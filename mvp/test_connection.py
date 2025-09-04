#!/usr/bin/env python3
"""
FreeSWITCH 连接测试脚本
用于测试 Genesis 库是否能正确连接到 FreeSWITCH
"""

import asyncio
import os
import sys
from genesis import Inbound, Consumer

# 配置
FS_HOST = os.getenv("FS_HOST", "freeswitch")
FS_PORT = int(os.getenv("FS_PORT", "8021"))
FS_PASSWORD = os.getenv("FS_PASSWORD", "ClueCon")

async def test_connection():
    """测试 FreeSWITCH 连接"""
    print(f"🔌 测试连接到 FreeSWITCH: {FS_HOST}:{FS_PORT}")
    print(f"🔑 密码: {FS_PASSWORD}")
    
    try:
        # 测试入站连接
        print("\n📡 测试入站连接...")
        inbound = Inbound(
            host=FS_HOST,
            port=FS_PORT,
            password=FS_PASSWORD
        )
        
        await inbound.start()
        print("✅ 入站连接成功")
        
        # 测试 API 命令
        print("\n🧪 测试 API 命令...")
        result = await inbound.api("version")
        print(f"✅ API 命令成功: {result}")
        
        # 测试消费者连接
        print("\n👂 测试消费者连接...")
        consumer = Consumer(
            host=FS_HOST,
            port=FS_PORT,
            password=FS_PASSWORD
        )
        
        await consumer.start()
        print("✅ 消费者连接成功")
        
        # 关闭连接
        await inbound.stop()
        await consumer.stop()
        
        print("\n🎉 所有连接测试通过！")
        return True
        
    except Exception as e:
        print(f"\n❌ 连接测试失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        return False

async def test_network():
    """测试网络连接"""
    import socket
    
    print(f"\n🌐 测试网络连接到 {FS_HOST}:{FS_PORT}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((FS_HOST, FS_PORT))
        sock.close()
        
        if result == 0:
            print("✅ 网络连接正常")
            return True
        else:
            print(f"❌ 网络连接失败，错误码: {result}")
            return False
    except Exception as e:
        print(f"❌ 网络测试异常: {e}")
        return False

async def main():
    """主函数"""
    print("🚀 FreeSWITCH 连接测试开始")
    print("=" * 50)
    
    # 测试网络连接
    network_ok = await test_network()
    
    if not network_ok:
        print("\n⚠️  网络连接失败，请检查:")
        print(f"   - FreeSWITCH 容器是否运行")
        print(f"   - 端口 {FS_PORT} 是否开放")
        print(f"   - 容器网络是否正确配置")
        return
    
    # 测试 Genesis 连接
    genesis_ok = await test_connection()
    
    if genesis_ok:
        print("\n🎯 建议:")
        print("   - 检查 MVP 应用的环境变量配置")
        print("   - 确保 Genesis 库版本兼容")
        print("   - 查看应用日志获取详细错误信息")
    else:
        print("\n🔧 故障排除:")
        print("   - 检查 FreeSWITCH 配置")
        print("   - 验证 event socket 模块加载")
        print("   - 确认密码设置正确")

if __name__ == "__main__":
    asyncio.run(main())
