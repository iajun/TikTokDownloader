"""
语音转文字服务模块
负责将音频文件转换为文字
使用S3存储，video_id作为文件名
支持标准 whisper 和 faster_whisper 两种模式
支持 CPU 和 GPU（CUDA）设备
"""

import whisper
import tempfile
from pathlib import Path
from typing import Optional, Literal, Union
from ..utils import S3Client
import json
from ..utils.task_queue import run_cpu_blocking

# 尝试导入 faster_whisper
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    WhisperModel = None

# 尝试导入 torch 以检测 CUDA 支持
try:
    import torch
    TORCH_AVAILABLE = True
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    TORCH_AVAILABLE = False
    CUDA_AVAILABLE = False


def _detect_device() -> str:
    """自动检测可用的设备，优先使用 GPU"""
    if CUDA_AVAILABLE:
        return "cuda"
    return "cpu"


def _map_model_name_for_faster_whisper(model_name: str) -> str:
    """
    将标准 whisper 的模型名称映射为 faster_whisper 支持的名称
    
    faster_whisper 不支持 -turbo 后缀，需要移除
    例如: "base" -> "large-v3"
    """
    # 移除 -turbo 后缀（如果存在）
    if model_name.endswith("-turbo"):
        return model_name[:-6]  # 移除 "-turbo"
    return model_name


# 进程内 Whisper 模型缓存，确保每个子进程仅加载一次模型
_WHISPER_MODELS = {}
_FASTER_WHISPER_MODELS = {}


def _whisper_transcribe(audio_path: str, model_name: str, device: str = "cpu") -> str:
    """在子进程中执行标准 Whisper 转录，并在该进程内缓存模型。"""
    cache_key = f"{model_name}_{device}"
    model = _WHISPER_MODELS.get(cache_key)
    if model is None:
        # 标准 whisper 通过 torch 支持 GPU
        if device == "cuda" and TORCH_AVAILABLE and CUDA_AVAILABLE:
            model = whisper.load_model(model_name, device="cuda")
        else:
            model = whisper.load_model(model_name, device="cpu")
        _WHISPER_MODELS[cache_key] = model
    result = model.transcribe(audio_path, language="zh", initial_prompt="")
    return result.get("text", "").strip()


# tiny, tiny.en, base, base.en,
#             small, small.en, distil-small.en, medium, medium.en, distil-medium.en, large-v1,
#             large-v2, large-v3, large, distil-large-v2, distil-large-v3, base, or turbo
def _faster_whisper_transcribe(audio_path: str, model_name: str, device: str = "cpu", compute_type: str = "int8") -> str:
    """在子进程中执行 Faster Whisper 转录，并在该进程内缓存模型。"""
    # 映射模型名称以适配 faster_whisper
    cache_key = f"{model_name}_{device}_{compute_type}"
    model = _FASTER_WHISPER_MODELS.get(cache_key)
    if model is None:
        if not FASTER_WHISPER_AVAILABLE:
            raise ImportError("faster_whisper 未安装，请使用 pip install faster-whisper")
        try:
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
            _FASTER_WHISPER_MODELS[cache_key] = model
        except Exception as e:
            # 如果模型加载失败，抛出异常以便上层处理
            raise RuntimeError(f"无法加载 faster_whisper 模型 {model_name}: {str(e)}") from e
    segments, info = model.transcribe(audio_path, language="zh", initial_prompt="")
    # 合并所有片段文本（segments 是一个生成器）
    text_parts = []
    for segment in segments:
        text_parts.append(segment.text)
    return " ".join(text_parts).strip()


def _transcribe_auto(audio_path: str, model_name: str = "base") -> str:
    """
    自动选择最佳的转录方法，优先使用 faster_whisper，如果不可用则回退到标准 whisper
    
    Args:
        audio_path: 音频文件路径
        model_name: 模型名称
        
    Returns:
        转录文本
    """
    device = _detect_device()
    
    # 优先尝试 faster_whisper
    if FASTER_WHISPER_AVAILABLE:
        try:
            # GPU 使用 float16，CPU 使用 int8
            compute_type = "float16" if device == "cuda" else "int8"
            result = _faster_whisper_transcribe(audio_path, model_name, device, compute_type)
            if result and result.strip():
                return result
            else:
                print("faster_whisper 转录结果为空，回退到标准 whisper")
        except (ImportError, RuntimeError, Exception) as e:
            error_msg = str(e)
            # 如果是模型下载/加载错误，给出更友好的提示
            if "Hub" in error_msg or "snapshot" in error_msg or "cannot find" in error_msg.lower():
                print(f"faster_whisper 模型加载失败（可能是网络问题或模型名称不匹配），回退到标准 whisper")
                print(f"错误详情: {error_msg}")
            else:
                print(f"faster_whisper 转录失败，回退到标准 whisper: {error_msg}")
    
    # 回退到标准 whisper
    return _whisper_transcribe(audio_path, model_name, device)


class TranscriptionService:
    """语音转文字服务"""
    
    def __init__(
        self, 
        model_name: str = "base",
        mode: Literal["whisper", "faster_whisper", "auto"] = "auto",
        device: str = "auto",
        compute_type: Optional[str] = None
    ):
        """
        初始化语音转文字服务
        
        Args:
            model_name: 模型名称，如 "base"
            mode: 转录模式，"auto"（优先 faster_whisper）、"whisper" 或 "faster_whisper"
            device: 设备类型，可选 "auto"（自动检测）、"cpu" 或 "cuda"
            compute_type: 计算类型，仅 faster_whisper 模式有效，可选 "int8", "int8_float16", "int16", "float16", "float32"
                        如果为 None，将根据设备自动选择（GPU 使用 float16，CPU 使用 int8）
        """
        self.whisper_model = None
        self.model_name = model_name
        
        # 处理设备选择
        if device == "auto":
            self.device = _detect_device()
            print(f"自动检测设备: {self.device}")
        else:
            self.device = device
        
        # 验证设备可用性
        if self.device == "cuda" and not CUDA_AVAILABLE:
            print(f"警告: CUDA 不可用，回退到 CPU")
            self.device = "cpu"
        
        # 处理模式选择：优先 faster_whisper
        if mode == "auto":
            if FASTER_WHISPER_AVAILABLE:
                self.mode = "faster_whisper"
                print("自动选择模式: faster_whisper（优先）")
            else:
                self.mode = "whisper"
                print("自动选择模式: whisper（faster_whisper 不可用）")
        else:
            self.mode = mode
        
        # 自动选择 compute_type
        if compute_type is None:
            if self.device == "cuda":
                self.compute_type = "float16"  # GPU 推荐使用 float16
            else:
                self.compute_type = "int8"  # CPU 推荐使用 int8
        else:
            self.compute_type = compute_type
        
        self.s3_client = S3Client()
        
        # 验证模式可用性
        if self.mode == "faster_whisper" and not FASTER_WHISPER_AVAILABLE:
            print("警告: faster_whisper 未安装，回退到标准 whisper 模式")
            print("安装命令: pip install faster-whisper")
            self.mode = "whisper"
        
        if self.mode == "whisper":
            self._load_model()
        else:
            device_str = "GPU" if self.device == "cuda" else "CPU"
            print(f"使用 faster_whisper 模式，设备: {device_str}，compute_type: {self.compute_type}，将在首次转录时加载模型")
    
    def _load_model(self):
        """加载标准 Whisper 模型（仅 whisper 模式使用）"""
        try:
            device_str = "GPU" if self.device == "cuda" else "CPU"
            print(f"正在加载Whisper模型: {self.model_name} (设备: {device_str})")
            if self.device == "cuda" and TORCH_AVAILABLE and CUDA_AVAILABLE:
                self.whisper_model = whisper.load_model(self.model_name, device="cuda")
            else:
                self.whisper_model = whisper.load_model(self.model_name, device="cpu")
            print("Whisper模型加载成功")
        except Exception as e:
            print(f"加载Whisper模型失败: {str(e)}")
            raise
    
    def transcribe(self, audio_path: str, video_id: str) -> Optional[str]:
        """
        同步语音转文字（使用进程池执行转录，支持 CPU 和 GPU）
        
        Args:
            audio_path: 音频文件路径
            video_id: 视频ID
            
        Returns:
            转录文本，失败返回 None
        """
        try:
            device_str = "GPU" if self.device == "cuda" else "CPU"
            if self.mode == "faster_whisper":
                print(f"正在转换音频为文字(faster_whisper, {device_str}): {audio_path}")
                raw_text = run_cpu_blocking(
                    _faster_whisper_transcribe, 
                    audio_path, 
                    self.model_name,
                    self.device,
                    self.compute_type
                )
            else:
                print(f"正在转换音频为文字(whisper, {device_str}): {audio_path}")
                raw_text = run_cpu_blocking(
                    _whisper_transcribe, 
                    audio_path, 
                    self.model_name,
                    self.device
                )
            
            text = (raw_text or "").strip()
            if text:
                print("语音转文字成功")
                return text
            print("未识别到有效内容")
            return None
        except Exception as e:
            print(f"语音转文字失败: {str(e)}")
            return None

