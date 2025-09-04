#!/usr/bin/env python3
"""
音频流测试脚本 - 测试 mod_audio_stream 插件功能
"""

import asyncio
import websockets
import json
import time
import sys
import os
from datetime import datetime

class AudioStreamTester:
    """音频流测试类"""
    
    def __init__(self, ws_host: str = "localhost", ws_port: int = 8081):
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.websocket = None
        self.audio_data = []
        self.test_results = {}
        
    async def connect_to_audio_stream(self, call_uuid: str):
        """连接到音频流"""
        try:
            ws_url = f"ws://{self.ws_host}:{self.ws_port}/audio/{call_uuid}"
            print(f"🔌 连接到音频流: {ws_url}")
            
            self.websocket = await websockets.connect(ws_url)
            print(f"✅ 音频流连接成功: {call_uuid}")
            
            return True
            
        except Exception as e:
            print(f"❌ 连接音频流失败: {e}")
            return False
    
    async def listen_to_audio_stream(self, duration: int = 10):
        """监听音频流"""
        if not self.websocket:
            print("❌ 未连接到音频流")
            return
        
        try:
            print(f"🎵 开始监听音频流，持续 {duration} 秒...")
            start_time = time.time()
            
            while time.time() - start_time < duration:
                try:
                    # 设置超时以避免无限等待
                    message = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=1.0
                    )
                    
                    if isinstance(message, bytes):
                        # 二进制音频数据
                        self.audio_data.append(message)
                        print(f"📡 收到音频数据: {len(message)} bytes, 总计: {len(self.audio_data)} 块")
                    else:
                        # 文本消息
                        print(f"📝 收到文本消息: {message}")
                        
                except asyncio.TimeoutError:
                    # 超时，继续循环
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print("🔌 音频流连接已关闭")
                    break
                    
        except Exception as e:
            print(f"❌ 监听音频流失败: {e}")
    
    async def close_connection(self):
        """关闭连接"""
        if self.websocket:
            await self.websocket.close()
            print("🔌 音频流连接已关闭")
    
    def analyze_audio_data(self):
        """分析音频数据"""
        if not self.audio_data:
            print("⚠️  没有收到音频数据")
            return
        
        total_bytes = sum(len(chunk) for chunk in self.audio_data)
        avg_chunk_size = total_bytes / len(self.audio_data)
        
        print(f"\n📊 音频数据分析:")
        print(f"   数据块数量: {len(self.audio_data)}")
        print(f"   总字节数: {total_bytes}")
        print(f"   平均块大小: {avg_chunk_size:.2f} bytes")
        print(f"   数据块大小范围: {min(len(chunk) for chunk in self.audio_data)} - {max(len(chunk) for chunk in self.audio_data)} bytes")
        
        # 保存音频数据用于分析
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audio_stream_test_{timestamp}.raw"
        
        try:
            with open(filename, 'wb') as f:
                for chunk in self.audio_data:
                    f.write(chunk)
            print(f"💾 音频数据已保存到: {filename}")
        except Exception as e:
            print(f"❌ 保存音频数据失败: {e}")
    
    async def run_test(self, call_uuid: str, duration: int = 10):
        """运行完整测试"""
        print(f"🚀 开始音频流测试")
        print(f"通话UUID: {call_uuid}")
        print(f"测试时长: {duration} 秒")
        print("-" * 50)
        
        try:
            # 1. 连接音频流
            if not await self.connect_to_audio_stream(call_uuid):
                return False
            
            # 2. 监听音频流
            await self.listen_to_audio_stream(duration)
            
            # 3. 分析结果
            self.analyze_audio_data()
            
            return True
            
        except Exception as e:
            print(f"❌ 测试执行失败: {e}")
            return False
        finally:
            # 4. 清理连接
            await self.close_connection()

async def main():
    """主函数"""
    print("🎵 FreeSWITCH 音频流测试工具")
    print("=" * 50)
    
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("用法: python test_audio_stream.py <call_uuid> [duration]")
        print("示例: python test_audio_stream.py 12345678-1234-1234-1234-123456789012 15")
        sys.exit(1)
    
    call_uuid = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    print(f"目标通话: {call_uuid}")
    print(f"测试时长: {duration} 秒")
    print()
    
    # 创建测试器并运行测试
    tester = AudioStreamTester()
    
    try:
        success = await tester.run_test(call_uuid, duration)
        
        if success:
            print("\n✅ 音频流测试完成!")
        else:
            print("\n❌ 音频流测试失败!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        sys.exit(1)
