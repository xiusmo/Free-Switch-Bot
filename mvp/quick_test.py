#!/usr/bin/env python3
"""
快速连接测试脚本
"""

import asyncio
import aiohttp
import json

async def test_endpoints():
    """测试各个端点"""
    base_url = "http://localhost:8080"
    
    print("🧪 测试 MVP 应用端点...")
    
    # 测试健康检查
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ 健康检查成功:")
                    print(f"   FreeSWITCH 连接: {data.get('freeswitch_connected')}")
                    print(f"   FS 主机: {data.get('fs_host')}")
                    print(f"   FS 端口: {data.get('fs_port')}")
                    print(f"   密码设置: {data.get('fs_password_set')}")
                    print(f"   活跃通话: {data.get('active_calls')}")
                    print(f"   音频流: {data.get('audio_streams')}")
                else:
                    print(f"❌ 健康检查失败: {response.status}")
    except Exception as e:
        print(f"❌ 健康检查异常: {e}")
    
    # 测试连接测试端点
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/test-connection") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"\n✅ 连接测试成功:")
                    print(f"   状态: {data.get('status')}")
                    print(f"   连接: {data.get('connected')}")
                    print(f"   消息: {data.get('message')}")
                    if 'version' in data:
                        print(f"   版本: {data.get('version')}")
                else:
                    print(f"\n❌ 连接测试失败: {response.status}")
    except Exception as e:
        print(f"\n❌ 连接测试异常: {e}")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
