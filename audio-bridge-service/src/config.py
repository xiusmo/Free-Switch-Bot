"""
Audio Bridge Service Configuration
音频桥接服务配置文件
"""
import os
from typing import Optional

class BridgeConfig:
    """音频桥接服务配置类"""
    
    # 服务端口配置
    BRIDGE_HOST: str = os.getenv("BRIDGE_HOST", "0.0.0.0")
    BRIDGE_PORT: int = int(os.getenv("BRIDGE_PORT", "8082"))
    
    # MVP连接配置
    MVP_WS_HOST: str = os.getenv("MVP_WS_HOST", "fs-mvp")
    MVP_WS_PORT: int = int(os.getenv("MVP_WS_PORT", "8081"))
    
    # RealtimeVoiceChat连接配置  
    RTVC_WS_HOST: str = os.getenv("RTVC_WS_HOST", "realtimevoicechat")
    RTVC_WS_PORT: int = int(os.getenv("RTVC_WS_PORT", "8000"))
    
    # 音频配置
    FREESWITCH_SAMPLE_RATE: int = 8000  # FreeSWITCH音频采样率
    RTVC_SAMPLE_RATE: int = 16000  # RealtimeVoiceChat期望采样率 (OpenAI API标准)
    AUDIO_CHANNELS: int = 1  # 单声道
    AUDIO_BUFFER_SIZE: int = 1024  # 音频缓冲区大小
    
    # 重采样配置
    UPSAMPLE_FACTOR: int = 2  # 8kHz -> 16kHz (2倍)
    DOWNSAMPLE_FACTOR: int = 2  # 16kHz -> 8kHz (1/2倍)
    
    # 会话管理配置
    SESSION_TIMEOUT: int = int(os.getenv("SESSION_TIMEOUT", "300"))  # 5分钟超时
    MAX_CONCURRENT_SESSIONS: int = int(os.getenv("MAX_SESSIONS", "10"))
    
    # WebSocket配置
    WS_PING_INTERVAL: int = 30  # WebSocket心跳间隔(秒)
    WS_PING_TIMEOUT: int = 10   # WebSocket超时时间(秒)
    WS_MAX_SIZE: Optional[int] = 1024 * 1024  # 1MB最大消息大小
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 调试配置
    DEBUG_MODE: bool = os.getenv("DEBUG", "false").lower() == "true"
    SAVE_AUDIO_DEBUG: bool = os.getenv("SAVE_AUDIO_DEBUG", "false").lower() == "true"
    DEBUG_AUDIO_PATH: str = "/tmp/audio_debug"

# 全局配置实例
config = BridgeConfig()
