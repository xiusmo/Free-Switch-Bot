#!/usr/bin/env python3
"""
FreeSWITCH 系统测试脚本
用于测试音频流、录音、播放和外呼功能
"""

import asyncio
import aiohttp
import json
import time
import sys
import os
from datetime import datetime

# 添加应用目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from config import config

class SystemTester:
    """系统测试类"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def test_health(self):
        """测试健康检查"""
        print("🔍 测试健康检查...")
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 健康检查通过: {data}")
                    return True
                else:
                    print(f"❌ 健康检查失败: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ 健康检查异常: {e}")
            return False
    
    async def test_get_calls(self):
        """测试获取通话列表"""
        print("📞 测试获取通话列表...")
        try:
            async with self.session.get(f"{self.base_url}/calls") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 获取通话列表成功: {len(data)} 个通话")
                    for call in data:
                        print(f"   - {call['call_uuid']}: {call['status']} -> {call['phone_number']}")
                    return True
                else:
                    print(f"❌ 获取通话列表失败: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ 获取通话列表异常: {e}")
            return False
    
    async def test_make_outbound_call(self, phone_number: str = "1001"):
        """测试外呼"""
        print(f"📤 测试外呼到 {phone_number}...")
        try:
            payload = {
                "phone_number": phone_number,
                "caller_id": "1000"
            }
            
            async with self.session.post(
                f"{self.base_url}/call/outbound",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 外呼成功: {data}")
                    return True
                else:
                    error_data = await response.text()
                    print(f"❌ 外呼失败: {response.status} - {error_data}")
                    return False
        except Exception as e:
            print(f"❌ 外呼异常: {e}")
            return False
    
    async def test_answer_call(self, call_uuid: str):
        """测试接听通话"""
        print(f"✅ 测试接听通话 {call_uuid}...")
        try:
            payload = {"call_uuid": call_uuid}
            
            async with self.session.post(
                f"{self.base_url}/call/answer",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 接听成功: {data}")
                    return True
                else:
                    error_data = await response.text()
                    print(f"❌ 接听失败: {response.status} - {error_data}")
                    return False
        except Exception as e:
            print(f"❌ 接听异常: {e}")
            return False
    
    async def test_hangup_call(self, call_uuid: str):
        """测试挂断通话"""
        print(f"📴 测试挂断通话 {call_uuid}...")
        try:
            payload = {"call_uuid": call_uuid}
            
            async with self.session.post(
                f"{self.base_url}/call/hangup",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 挂断成功: {data}")
                    return True
                else:
                    error_data = await response.text()
                    print(f"❌ 挂断失败: {response.status} - {error_data}")
                    return False
        except Exception as e:
            print(f"❌ 挂断异常: {e}")
            return False
    
    async def test_get_recordings(self):
        """测试获取录音列表"""
        print("💾 测试获取录音列表...")
        try:
            async with self.session.get(f"{self.base_url}/recordings") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 获取录音列表成功: {len(data['recordings'])} 个录音文件")
                    for recording in data['recordings']:
                        print(f"   - {recording['filename']}: {recording['size']} bytes")
                    return True
                else:
                    print(f"❌ 获取录音列表失败: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ 获取录音列表异常: {e}")
            return False
    
    async def test_get_call_recording(self, call_uuid: str):
        """测试获取特定通话的录音"""
        print(f"🎵 测试获取通话录音 {call_uuid}...")
        try:
            async with self.session.get(f"{self.base_url}/call/{call_uuid}/recording") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 获取通话录音成功: {len(data['recordings'])} 个录音文件")
                    for recording in data['recordings']:
                        print(f"   - {recording}")
                    return True
                else:
                    print(f"❌ 获取通话录音失败: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ 获取通话录音异常: {e}")
            return False
    
    async def run_full_test(self):
        """运行完整测试"""
        print("🚀 开始系统测试...")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"目标服务: {self.base_url}")
        print("-" * 50)
        
        # 测试健康检查
        if not await self.test_health():
            print("❌ 系统健康检查失败，停止测试")
            return False
        
        print()
        
        # 测试获取通话列表
        await self.test_get_calls()
        
        print()
        
        # 测试外呼
        if await self.test_make_outbound_call():
            print("⏳ 等待通话建立...")
            await asyncio.sleep(5)
            
            # 获取当前通话
            async with self.session.get(f"{self.base_url}/calls") as response:
                if response.status == 200:
                    calls = await response.json()
                    if calls:
                        call_uuid = calls[0]['call_uuid']
                        
                        # 测试接听
                        await self.test_answer_call(call_uuid)
                        
                        print("⏳ 等待音频播放...")
                        await asyncio.sleep(10)
                        
                        # 测试挂断
                        await self.test_hangup_call(call_uuid)
                        
                        print("⏳ 等待通话结束...")
                        await asyncio.sleep(5)
        
        print()
        
        # 测试录音功能
        await self.test_get_recordings()
        
        print()
        print("✅ 系统测试完成!")
        return True

async def main():
    """主函数"""
    print("FreeSWITCH 系统测试工具")
    print("=" * 50)
    
    # 检查命令行参数
    base_url = "http://localhost:8080"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    print(f"使用服务地址: {base_url}")
    
    async with SystemTester(base_url) as tester:
        await tester.run_full_test()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        sys.exit(1)
