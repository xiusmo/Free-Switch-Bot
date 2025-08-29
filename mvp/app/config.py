import os
from typing import Optional

class Config:
    """应用配置类"""
    
    # FreeSWITCH 连接配置
    FS_HOST: str = os.getenv("FS_HOST", "localhost")
    FS_PORT: int = int(os.getenv("FS_PORT", "8021"))
    FS_PASSWORD: str = os.getenv("FS_PASSWORD", "ClueCon")
    
    # 应用配置
    PORT: int = int(os.getenv("PORT", "8080"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # 音频配置
    AUDIO_SAMPLE_RATE: int = int(os.getenv("AUDIO_SAMPLE_RATE", "8000"))
    AUDIO_CHANNELS: int = int(os.getenv("AUDIO_CHANNELS", "1"))
    AUDIO_BIT_DEPTH: int = int(os.getenv("AUDIO_BIT_DEPTH", "16"))
    # 音频 WebSocket 服务（供 FreeSWITCH 连接）
    AUDIO_WS_HOST: str = os.getenv("AUDIO_WS_HOST", "fs-mvp")  # 在 docker-compose 网络中使用容器名访问
    AUDIO_WS_PORT: int = int(os.getenv("AUDIO_WS_PORT", "8081"))
    
    # 录音配置
    RECORDING_DIR: str = os.getenv("RECORDING_DIR", "/app/recordings")
    MAX_RECORDING_SIZE: int = int(os.getenv("MAX_RECORDING_SIZE", "100"))  # MB
    RECORDING_RETENTION_DAYS: int = int(os.getenv("RECORDING_RETENTION_DAYS", "30"))
    
    # 上传目录（用于外呼播放的音频文件临时存放，建议与 FreeSWITCH 共享卷映射）
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/shared/recordings")

    # UCM 对接 IP（用于直拨回退）
    UCM_IP: str = os.getenv("UCM_IP", "172.16.100.101")
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # 安全配置
    API_KEY: Optional[str] = os.getenv("API_KEY")
    ENABLE_AUTH: bool = os.getenv("ENABLE_AUTH", "false").lower() == "true"
    
    # 音频文件路径
    EXAMPLE_AUDIO_FILE: str = os.getenv("EXAMPLE_AUDIO_FILE", "/app/wav-example.wav")
    
    # Qwen-Omni 实时API配置
    QWEN_OMNI_API_KEY: Optional[str] = os.getenv("QWEN_OMNI_API_KEY", "sk-a8fb7798b99e458f8a0ecf43684466ff")
    QWEN_OMNI_MODEL: str = os.getenv("QWEN_OMNI_MODEL", "qwen-omni-turbo-realtime")
    QWEN_OMNI_VOICE: str = os.getenv("QWEN_OMNI_VOICE", "Chelsie")  # Chelsie, Serena, Ethan, Cherry
    QWEN_OMNI_LANGUAGE: str = os.getenv("QWEN_OMNI_LANGUAGE", "zh")  # zh, en
    QWEN_OMNI_VAD_MODE: bool = os.getenv("QWEN_OMNI_VAD_MODE", "true").lower() == "true"
    QWEN_OMNI_WEBSOCKET_URL: str = os.getenv("QWEN_OMNI_WEBSOCKET_URL", "wss://dashscope.aliyuncs.com/api/v1/apps/omni/realtime")
    QWEN_OMNI_ENABLED: bool = os.getenv("QWEN_OMNI_ENABLED", "false").lower() == "true"
    
    @classmethod
    def validate(cls) -> bool:
        """验证配置"""
        required_dirs = [cls.RECORDING_DIR, cls.UPLOAD_DIR]
        
        for directory in required_dirs:
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                except Exception as e:
                    print(f"无法创建目录 {directory}: {e}")
                    return False
        
        return True
    
    @classmethod
    def get_fs_connection_string(cls) -> str:
        """获取 FreeSWITCH 连接字符串"""
        return f"{cls.FS_HOST}:{cls.FS_PORT}"
    
    @classmethod
    def get_audio_config(cls) -> dict:
        """获取音频配置"""
        return {
            "sample_rate": cls.AUDIO_SAMPLE_RATE,
            "channels": cls.AUDIO_CHANNELS,
            "bit_depth": cls.AUDIO_BIT_DEPTH
        }

# 创建全局配置实例
config = Config()
