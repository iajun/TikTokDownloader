"""
异步任务队列管理器
支持任务优先级、并发控制和状态管理
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from collections import deque
import heapq


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class QueuedTask:
    """队列中的任务"""
    task_id: int
    priority: TaskPriority
    created_at: datetime
    retry_count: int = 0
    max_retries: int = 3
    
    def __lt__(self, other):
        """用于优先级队列排序"""
        if self.priority != other.priority:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at


class AsyncTaskQueue:
    """异步任务队列管理器"""
    
    def __init__(self, max_concurrent: int = 5):
        """
        初始化异步任务队列
        
        Args:
            max_concurrent: 最大并发任务数
        """
        self.max_concurrent = max_concurrent
        self.priority_queue: List[QueuedTask] = []  # 使用堆实现优先级队列
        self.active_tasks: Dict[int, asyncio.Task] = {}
        self.task_handlers: Dict[int, callable] = {}
        self.task_status: Dict[int, str] = {}  # task_id -> status
        self.lock = asyncio.Lock()
        self.running = False
        self._processing_task: Optional[asyncio.Task] = None
    
    async def enqueue(
        self,
        task_id: int,
        handler: callable,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3
    ):
        """
        将任务加入队列
        
        Args:
            task_id: 任务ID
            handler: 任务处理函数（async）
            priority: 任务优先级
            max_retries: 最大重试次数
        """
        async with self.lock:
            queued_task = QueuedTask(
                task_id=task_id,
                priority=priority,
                created_at=datetime.utcnow(),
                max_retries=max_retries
            )
            heapq.heappush(self.priority_queue, queued_task)
            self.task_handlers[task_id] = handler
            self.task_status[task_id] = "queued"
            print(f"Task {task_id} enqueued with priority {priority.name}")
    
    async def dequeue(self) -> Optional[QueuedTask]:
        """从队列中取出优先级最高的任务"""
        async with self.lock:
            if not self.priority_queue:
                return None
            return heapq.heappop(self.priority_queue)
    
    async def start(self):
        """启动任务队列处理器"""
        if self.running:
            print("Task queue is already running")
            return
        
        self.running = True
        self._processing_task = asyncio.create_task(self._process_loop())
        print(f"Async task queue started (max_concurrent={self.max_concurrent})")
    
    async def stop(self):
        """停止任务队列处理器"""
        print("Stopping async task queue...")
        self.running = False
        
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        # 等待所有活跃任务完成
        if self.active_tasks:
            print(f"Waiting for {len(self.active_tasks)} active tasks to complete...")
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
        
        print("Async task queue stopped")
    
    async def _process_loop(self):
        """主处理循环"""
        while self.running:
            try:
                # 清理已完成的任务
                await self._cleanup_completed_tasks()
                
                # 如果有空闲槽位，从队列中取出任务并处理
                while len(self.active_tasks) < self.max_concurrent and self.running:
                    queued_task = await self.dequeue()
                    
                    if queued_task is None:
                        # 队列为空，等待一段时间
                        break
                    
                    task_id = queued_task.task_id
                    handler = self.task_handlers.get(task_id)
                    
                    if handler is None:
                        print(f"Warning: No handler found for task {task_id}")
                        continue
                    
                    # 创建异步任务
                    print(f"Starting task {task_id} (priority: {queued_task.priority.name})")
                    self.task_status[task_id] = "processing"
                    task = asyncio.create_task(self._execute_task(queued_task, handler))
                    self.active_tasks[task_id] = task
                
                # 等待一段时间后继续
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Error in task queue processing loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(5)
    
    async def _execute_task(self, queued_task: QueuedTask, handler: callable):
        """执行任务"""
        task_id = queued_task.task_id
        
        try:
            # 执行任务处理函数
            result = await handler(task_id)
            
            if result:
                # 任务成功完成
                self.task_status[task_id] = "completed"
                print(f"Task {task_id} completed successfully")
            else:
                # 任务失败，检查是否需要重试
                if queued_task.retry_count < queued_task.max_retries:
                    queued_task.retry_count += 1
                    queued_task.created_at = datetime.utcnow()  # 更新重试时间
                    
                    # 重新加入队列
                    async with self.lock:
                        heapq.heappush(self.priority_queue, queued_task)
                    
                    self.task_status[task_id] = f"retrying ({queued_task.retry_count}/{queued_task.max_retries})"
                    print(f"Task {task_id} failed, will retry ({queued_task.retry_count}/{queued_task.max_retries})")
                else:
                    # 达到最大重试次数
                    self.task_status[task_id] = "failed"
                    print(f"Task {task_id} failed after {queued_task.max_retries} retries")
            
            # 清理处理函数引用
            self.task_handlers.pop(task_id, None)
            
        except Exception as e:
            print(f"Error executing task {task_id}: {e}")
            import traceback
            traceback.print_exc()
            
            # 检查是否需要重试
            if queued_task.retry_count < queued_task.max_retries:
                queued_task.retry_count += 1
                queued_task.created_at = datetime.utcnow()
                
                async with self.lock:
                    heapq.heappush(self.priority_queue, queued_task)
                
                self.task_status[task_id] = f"retrying ({queued_task.retry_count}/{queued_task.max_retries})"
            else:
                self.task_status[task_id] = "failed"
                self.task_handlers.pop(task_id, None)
    
    async def _cleanup_completed_tasks(self):
        """清理已完成的任务"""
        completed_task_ids = [
            task_id for task_id, task in self.active_tasks.items()
            if task.done()
        ]
        
        for task_id in completed_task_ids:
            task = self.active_tasks.pop(task_id, None)
            if task:
                try:
                    await task  # 获取结果，清除异常
                except Exception:
                    pass  # 异常已在 _execute_task 中处理
    
    async def get_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        async with self.lock:
            return {
                "running": self.running,
                "max_concurrent": self.max_concurrent,
                "queue_size": len(self.priority_queue),
                "active_tasks_count": len(self.active_tasks),
                "active_task_ids": list(self.active_tasks.keys()),
                "task_statuses": dict(self.task_status)
            }
    
    async def cancel_task(self, task_id: int) -> bool:
        """取消任务"""
        async with self.lock:
            # 如果任务在队列中，移除它
            new_queue = [
                task for task in self.priority_queue
                if task.task_id != task_id
            ]
            self.priority_queue = new_queue
            heapq.heapify(self.priority_queue)
            
            # 如果任务正在处理，取消它
            if task_id in self.active_tasks:
                task = self.active_tasks.pop(task_id)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                return True
            
            # 移除状态和处理器
            self.task_status.pop(task_id, None)
            self.task_handlers.pop(task_id, None)
            return True


# 全局任务队列实例
_global_async_queue: Optional[AsyncTaskQueue] = None


def get_async_task_queue(max_concurrent: int = 5) -> AsyncTaskQueue:
    """获取全局异步任务队列实例（与 task_queue 模块区分）"""
    global _global_async_queue
    if _global_async_queue is None:
        _global_async_queue = AsyncTaskQueue(max_concurrent=max_concurrent)
    return _global_async_queue

