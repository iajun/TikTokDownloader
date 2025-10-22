"""
异步任务队列模块
提供线程池与进程池的统一接口，便于在异步代码中调度高 CPU/GPU 与 I/O 任务。

用法示例：
    from ..utils.task_queue import get_task_queue

    queue = get_task_queue()
    # 提交 CPU 密集任务（进程池）
    result = await queue.submit_cpu(cpu_func, *args, **kwargs)

    # 提交 I/O 阻塞任务（线程池）
    result = await queue.submit_io(io_func, *args, **kwargs)

该模块会维护单例队列并支持优雅关闭。
"""

from __future__ import annotations

import os
import atexit
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Any, Callable, Optional


class TaskQueue:
    """统一的任务队列，封装线程池与进程池，并提供异步提交接口。"""

    def __init__(
        self,
        max_workers_io: Optional[int] = None,
        max_workers_cpu: Optional[int] = None,
        mp_start_method: Optional[str] = None,
    ) -> None:
        # 默认线程池大小：min(32, os.cpu_count() * 5) 以覆盖高并发 I/O
        if max_workers_io is None:
            cpu_cnt = os.cpu_count() or 4
            max_workers_io = min(32, cpu_cnt * 5)

        # 默认进程池大小：max(1, os.cpu_count() - 1)
        if max_workers_cpu is None:
            cpu_cnt = os.cpu_count() or 2
            max_workers_cpu = max(1, cpu_cnt - 1)

        if mp_start_method:
            try:
                import multiprocessing as _mp
                _mp.set_start_method(mp_start_method, force=True)
            except Exception:
                # 忽略启动方法设置失败，保持兼容
                pass

        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers_io, thread_name_prefix="io-worker")
        self._process_pool = ProcessPoolExecutor(max_workers=max_workers_cpu)
        self._closed = False

    async def submit_io(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """在共享线程池中执行阻塞 I/O 函数，返回异步结果。"""
        self._ensure_open()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._thread_pool, _callable_wrapper, func, args, kwargs)

    async def submit_cpu(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """在共享进程池中执行 CPU 密集函数，返回异步结果。"""
        self._ensure_open()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._process_pool, _callable_wrapper, func, args, kwargs)

    def shutdown(self, wait: bool = True) -> None:
        """优雅关闭线程池与进程池。"""
        if self._closed:
            return
        self._thread_pool.shutdown(wait=wait, cancel_futures=True)
        self._process_pool.shutdown(wait=wait, cancel_futures=True)
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("TaskQueue has been shut down")

    def run_io_blocking(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """在共享线程池中以阻塞方式运行函数，返回结果。
        适用于上层必须同步接口但又需要复用线程池的场景。
        """
        self._ensure_open()
        future = self._thread_pool.submit(_callable_wrapper, func, args, kwargs)
        return future.result()

    def run_cpu_blocking(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """在共享进程池中以阻塞方式运行 CPU 密集型函数，返回结果。"""
        self._ensure_open()
        future = self._process_pool.submit(_callable_wrapper, func, args, kwargs)
        return future.result()

    def submit_io_nonblocking(self, func: Callable[..., Any], *args: Any, **kwargs: Any):
        """非阻塞地将 I/O 任务提交到线程池，返回 Future。"""
        self._ensure_open()
        return self._thread_pool.submit(_callable_wrapper, func, args, kwargs)

    def submit_cpu_nonblocking(self, func: Callable[..., Any], *args: Any, **kwargs: Any):
        """非阻塞地将 CPU 任务提交到进程池，返回 Future。"""
        self._ensure_open()
        return self._process_pool.submit(_callable_wrapper, func, args, kwargs)


def _callable_wrapper(func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    """在执行器中调用目标函数，统一包装入参，便于 run_in_executor 传递。"""
    return func(*args, **kwargs)


_global_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """获取全局单例 TaskQueue。"""
    global _global_queue
    if _global_queue is None:
        # 允许通过环境变量配置规模
        io_workers = _int_from_env("AI_QUEUE_IO_WORKERS")
        cpu_workers = _int_from_env("AI_QUEUE_CPU_WORKERS")
        mp_method = os.getenv("AI_QUEUE_MP_START", None)

        _set = TaskQueue(
            max_workers_io=io_workers,
            max_workers_cpu=cpu_workers,
            mp_start_method=mp_method,
        )
        _global_queue = _set

        # 进程退出时优雅关闭
        atexit.register(lambda: _safe_shutdown(_set))

    return _global_queue


def _safe_shutdown(queue: TaskQueue) -> None:
    try:
        queue.shutdown(wait=False)
    except Exception:
        pass


def _int_from_env(name: str) -> Optional[int]:
    try:
        value = os.getenv(name, "").strip()
        if value == "":
            return None
        num = int(value)
        return num if num > 0 else None
    except Exception:
        return None


async def run_cpu_bound(func: Callable[..., Any], *args: Any, timeout: Optional[float] = None, **kwargs: Any) -> Any:
    """辅助方法：将 CPU 密集函数提交到全局进程池，可选超时。"""
    queue = get_task_queue()
    coro = queue.submit_cpu(func, *args, **kwargs)
    return await (asyncio.wait_for(coro, timeout=timeout) if timeout else coro)


async def run_io_bound(func: Callable[..., Any], *args: Any, timeout: Optional[float] = None, **kwargs: Any) -> Any:
    """辅助方法：将阻塞 I/O 函数提交到全局线程池，可选超时。"""
    queue = get_task_queue()
    coro = queue.submit_io(func, *args, **kwargs)
    return await (asyncio.wait_for(coro, timeout=timeout) if timeout else coro)


def run_io_blocking(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """辅助方法：在共享线程池中同步执行阻塞 I/O 函数。"""
    queue = get_task_queue()
    return queue.run_io_blocking(func, *args, **kwargs)


def run_cpu_blocking(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """辅助方法：在共享进程池中同步执行 CPU 密集型函数。"""
    queue = get_task_queue()
    return queue.run_cpu_blocking(func, *args, **kwargs)


def run_coro_blocking(coro_func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """在共享线程池中以阻塞方式运行协程函数。
    注意：该方法会在工作线程内创建并运行一个新的事件循环。
    """
    def _runner(fn: Callable[..., Any], f_args: tuple[Any, ...], f_kwargs: dict[str, Any]) -> Any:
        import asyncio as _asyncio
        return _asyncio.run(fn(*f_args, **f_kwargs))

    return run_io_blocking(_runner, coro_func, args, kwargs)


def submit_io_nonblocking(func: Callable[..., Any], *args: Any, **kwargs: Any):
    """非阻塞地提交 I/O 任务到共享线程池，返回 Future。"""
    queue = get_task_queue()
    return queue.submit_io_nonblocking(func, *args, **kwargs)


def submit_cpu_nonblocking(func: Callable[..., Any], *args: Any, **kwargs: Any):
    """非阻塞地提交 CPU 任务到共享进程池，返回 Future。"""
    queue = get_task_queue()
    return queue.submit_cpu_nonblocking(func, *args, **kwargs)


