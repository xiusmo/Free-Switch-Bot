#!/usr/bin/env python3
"""
Qwen-Omni集成测试脚本
用于测试音频流对接功能
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from app.qwen_omni_client import QwenOmniClient, QwenOmniAudioProcessor
from app import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_qwen_omni_connection():
    """测试Qwen-Omni连接"""
    print("🔍 测试Qwen-Omni连接...")
    
    # 检查配置
    if not config.config.QWEN_OMNI_API_KEY:
        print("❌ QWEN_OMNI_API_KEY未配置")
        return False
    
    call_uuid = "test-call-12345"
    client = QwenOmniClient(call_uuid)
    
    try:
        # 尝试连接
        success = await client.connect()
        if success:
            print("✅ Qwen-Omni连接成功")
            
            # 发送测试文本
            await client.send_text("你好，这是一个测试消息")
            print("📤 测试消息已发送")
            
            # 等待一段时间接收响应
            await asyncio.sleep(3)
            
            await client.close()
            print("🔌 连接已关闭")
            return True
        else:
            print("❌ Qwen-Omni连接失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

async def test_audio_processor():
    """测试音频处理器"""
    print("\n🔍 测试音频处理器...")
    
    call_uuid = "test-audio-12345"
    processor = QwenOmniAudioProcessor(call_uuid)
    
    # 设置音频响应回调
    def on_ai_audio(audio_data: bytes):
        print(f"🎵 收到AI音频响应: {len(audio_data)} bytes")
    
    processor.on_ai_audio = on_ai_audio
    
    try:
        # 启动处理器
        success = await processor.start()
        if success:
            print("✅ 音频处理器启动成功")
            
            # 模拟发送音频数据
            test_audio = b'\x00' * 320  # 20ms的静音数据 (8kHz, 16-bit, mono)
            await processor.process_incoming_audio(test_audio)
            print("📤 测试音频数据已发送")
            
            # 等待处理
            await asyncio.sleep(2)
            
            await processor.stop()
            print("⏹️ 音频处理器已停止")
            return True
        else:
            print("❌ 音频处理器启动失败")
            return False
            
    except Exception as e:
        print(f"❌ 音频处理器测试异常: {e}")
        return False

async def test_configuration():
    """测试配置"""
    print("\n🔍 测试配置...")
    
    print(f"QWEN_OMNI_ENABLED: {config.config.QWEN_OMNI_ENABLED}")
    print(f"QWEN_OMNI_MODEL: {config.config.QWEN_OMNI_MODEL}")
    print(f"QWEN_OMNI_VOICE: {config.config.QWEN_OMNI_VOICE}")
    print(f"QWEN_OMNI_LANGUAGE: {config.config.QWEN_OMNI_LANGUAGE}")
    print(f"QWEN_OMNI_VAD_MODE: {config.config.QWEN_OMNI_VAD_MODE}")
    print(f"QWEN_OMNI_API_KEY: {'***已配置***' if config.config.QWEN_OMNI_API_KEY else '未配置'}")
    
    return True

async def main():
    """主测试函数"""
    print("🚀 Qwen-Omni集成测试开始")
    print("=" * 50)
    
    # 测试配置
    await test_configuration()
    
    # 如果API Key未配置，跳过连接测试
    if not config.config.QWEN_OMNI_API_KEY:
        print("\n⚠️ 跳过连接测试（API Key未配置）")
        print("\n📋 配置说明：")
        print("1. 复制 env.example 到 .env")
        print("2. 设置 QWEN_OMNI_ENABLED=true")
        print("3. 设置 QWEN_OMNI_API_KEY=你的API密钥")
        return
    
    # 测试连接
    connection_success = await test_qwen_omni_connection()
    
    # 测试音频处理器
    if connection_success:
        await test_audio_processor()
    
    print("\n" + "=" * 50)
    print("🏁 测试完成")

if __name__ == "__main__":
    asyncio.run(main())
