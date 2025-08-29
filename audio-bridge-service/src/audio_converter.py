"""
Audio Format Converter
音频格式转换器 - 处理8kHz和48kHz之间的转换
"""
import asyncio
import logging
import struct
import time
from typing import Optional, Tuple
import numpy as np
from scipy.signal import resample_poly
from .config import config

logger = logging.getLogger(__name__)

class AudioConverter:
    """音频格式转换器"""
    
    def __init__(self):
        """初始化音频转换器"""
        self.freeswitch_sr = config.FREESWITCH_SAMPLE_RATE  # 8kHz
        self.rtvc_sr = config.RTVC_SAMPLE_RATE  # 16kHz
        self.channels = config.AUDIO_CHANNELS  # 单声道
        
        # 计算重采样参数
        self.up_factor = self.rtvc_sr // self.freeswitch_sr  # 2倍上采样
        self.down_factor = self.rtvc_sr // self.freeswitch_sr  # 2倍下采样
        
        logger.info(f"🔄 音频转换器初始化: {self.freeswitch_sr}Hz ↔ {self.rtvc_sr}Hz")
        
        # 调试模式下保存音频文件
        if config.SAVE_AUDIO_DEBUG:
            import os
            os.makedirs(config.DEBUG_AUDIO_PATH, exist_ok=True)
            self.debug_counter = 0
    
    def pcm_to_numpy(self, pcm_data: bytes, sample_rate: int) -> np.ndarray:
        """将PCM字节数据转换为numpy数组
        
        Args:
            pcm_data: PCM字节数据 (16-bit)
            sample_rate: 采样率
            
        Returns:
            numpy音频数组
        """
        if len(pcm_data) == 0:
            return np.array([], dtype=np.float32)
            
        # 转换为int16数组
        try:
            audio_int16 = np.frombuffer(pcm_data, dtype=np.int16)
        except ValueError as e:
            logger.warning(f"PCM数据转换失败: {e}")
            return np.array([], dtype=np.float32)
            
        # 转换为float32并归一化到[-1, 1]
        audio_float = audio_int16.astype(np.float32) / 32768.0
        
        return audio_float
    
    def numpy_to_pcm(self, audio_array: np.ndarray) -> bytes:
        """将numpy数组转换为PCM字节数据
        
        Args:
            audio_array: numpy音频数组 (float32, [-1, 1])
            
        Returns:
            PCM字节数据 (16-bit)
        """
        if len(audio_array) == 0:
            return b""
            
        # 限制到[-1, 1]范围
        audio_clipped = np.clip(audio_array, -1.0, 1.0)
        
        # 转换为int16
        audio_int16 = (audio_clipped * 32767).astype(np.int16)
        
        # 转换为字节
        return audio_int16.tobytes()
    
    def upsample_8k_to_16k(self, pcm_8k: bytes) -> bytes:
        """8kHz PCM上采样到16kHz PCM
        
        Args:
            pcm_8k: 8kHz PCM数据
            
        Returns:
            16kHz PCM数据
        """
        if len(pcm_8k) == 0:
            return b""
            
        # 转换为numpy数组
        audio_8k = self.pcm_to_numpy(pcm_8k, self.freeswitch_sr)
        if len(audio_8k) == 0:
            return b""
            
        # 使用scipy进行重采样 (2倍上采样)
        try:
            audio_16k = resample_poly(audio_8k, self.up_factor, 1)
        except Exception as e:
            logger.error(f"上采样失败: {e}")
            return b""
            
        # 转换回PCM
        pcm_16k = self.numpy_to_pcm(audio_16k)
        
        if config.SAVE_AUDIO_DEBUG:
            self._save_debug_audio(pcm_8k, pcm_16k, "upsample")
            
        logger.debug(f"上采样: {len(pcm_8k)} -> {len(pcm_16k)} bytes")
        return pcm_16k
    
    def downsample_16k_to_8k(self, pcm_16k: bytes) -> bytes:
        """16kHz PCM下采样到8kHz PCM
        
        Args:
            pcm_16k: 16kHz PCM数据
            
        Returns:
            8kHz PCM数据  
        """
        if len(pcm_16k) == 0:
            return b""
            
        # 转换为numpy数组
        audio_16k = self.pcm_to_numpy(pcm_16k, self.rtvc_sr)
        if len(audio_16k) == 0:
            return b""
            
        # 使用scipy进行重采样 (1/2倍下采样)
        try:
            audio_8k = resample_poly(audio_16k, 1, self.down_factor)
        except Exception as e:
            logger.error(f"下采样失败: {e}")
            return b""
            
        # 转换回PCM
        pcm_8k = self.numpy_to_pcm(audio_8k)
        
        if config.SAVE_AUDIO_DEBUG:
            self._save_debug_audio(pcm_16k, pcm_8k, "downsample")
            
        logger.debug(f"下采样: {len(pcm_16k)} -> {len(pcm_8k)} bytes")
        return pcm_8k
    
    def create_rtvc_audio_message(self, pcm_16k: bytes, timestamp_ms: Optional[int] = None) -> bytes:
        """创建RealtimeVoiceChat格式的音频消息
        
        Args:
            pcm_16k: 16kHz PCM数据
            timestamp_ms: 时间戳(毫秒)，None时使用当前时间
            
        Returns:
            RTVC格式的音频消息 (header + PCM)
        """
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)
            
        # 创建8字节头部: 4字节时间戳 + 4字节标志
        flags = 0  # TTS不播放标志
        header = struct.pack("!II", timestamp_ms, flags)
        
        return header + pcm_16k
    
    def parse_rtvc_audio_message(self, message: bytes) -> Tuple[Optional[bytes], Optional[int], Optional[int]]:
        """解析RealtimeVoiceChat格式的音频消息
        
        Args:
            message: RTVC音频消息
            
        Returns:
            (PCM数据, 时间戳, 标志)，解析失败返回(None, None, None)
        """
        if len(message) < 8:
            logger.warning(f"RTVC消息头部不完整: {len(message)} < 8 bytes")
            return None, None, None
            
        try:
            # 解析8字节头部
            timestamp_ms, flags = struct.unpack("!II", message[:8])
            pcm_data = message[8:]
            
            return pcm_data, timestamp_ms, flags
            
        except struct.error as e:
            logger.error(f"RTVC消息解析失败: {e}")
            return None, None, None
    
    def _save_debug_audio(self, input_pcm: bytes, output_pcm: bytes, operation: str):
        """保存调试音频文件"""
        try:
            import wave
            
            # 输入文件
            input_path = f"{config.DEBUG_AUDIO_PATH}/{operation}_input_{self.debug_counter}.wav"
            with wave.open(input_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.freeswitch_sr if operation == "upsample" else self.rtvc_sr)
                wav_file.writeframes(input_pcm)
            
            # 输出文件  
            output_path = f"{config.DEBUG_AUDIO_PATH}/{operation}_output_{self.debug_counter}.wav"
            with wave.open(output_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit  
                wav_file.setframerate(self.rtvc_sr if operation == "upsample" else self.freeswitch_sr)
                wav_file.writeframes(output_pcm)
                
            self.debug_counter += 1
            
        except Exception as e:
            logger.error(f"保存调试音频失败: {e}")
