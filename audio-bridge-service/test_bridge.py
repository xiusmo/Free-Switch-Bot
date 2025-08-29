#!/usr/bin/env python3
"""
Audio Bridge Service Test Script
音频桥接服务测试脚本
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any
import httpx

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BridgeServiceTester:
    """桥接服务测试类"""
    
    def __init__(self, bridge_host: str = "localhost", bridge_port: int = 8082):
        self.base_url = f"http://{bridge_host}:{bridge_port}"
        
    async def test_health_check(self) -> bool:
        """测试健康检查"""
        logger.info("🏥 测试健康检查...")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health")
                
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ 健康检查通过: {data['status']}")
                logger.info(f"📊 当前会话: {data['sessions']['active']}/{data['sessions']['max']}")
                return True
            else:
                logger.error(f"❌ 健康检查失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 健康检查异常: {e}")
            return False
    
    async def test_service_info(self) -> bool:
        """测试服务基本信息"""
        logger.info("ℹ️  测试服务信息...")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/")
                
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ 服务信息: {data['service']} v{data['version']}")
                logger.info(f"🔗 MVP: {data['config']['mvp_host']}:{data['config']['mvp_port']}")
                logger.info(f"🤖 RTVC: {data['config']['rtvc_host']}:{data['config']['rtvc_port']}")
                return True
            else:
                logger.error(f"❌ 服务信息获取失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 服务信息异常: {e}")
            return False
    
    async def test_start_bridge(self, call_uuid: str = None, phone_number: str = "1001") -> str:
        """测试启动桥接会话"""
        if call_uuid is None:
            call_uuid = str(uuid.uuid4())
            
        logger.info(f"🚀 测试启动桥接: {call_uuid}")
        
        try:
            request_data = {
                "call_uuid": call_uuid,
                "phone_number": phone_number
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/bridge/start",
                    json=request_data
                )
                
            if response.status_code == 200:
                data = response.json()
                if data['success']:
                    session_id = data['session_id']
                    logger.info(f"✅ 桥接启动成功: {session_id}")
                    return session_id
                else:
                    logger.error(f"❌ 桥接启动失败: {data['message']}")
                    return None
            else:
                logger.error(f"❌ 桥接启动请求失败: {response.status_code}")
                logger.error(f"响应: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 桥接启动异常: {e}")
            return None
    
    async def test_session_info(self, session_id: str) -> bool:
        """测试获取会话信息"""
        logger.info(f"📋 测试会话信息: {session_id}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/sessions/{session_id}")
                
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ 会话状态: {data['state']}")
                logger.info(f"📞 通话UUID: {data['call_uuid']}")
                logger.info(f"📱 电话号码: {data['phone_number']}")
                logger.info(f"⏱️  持续时间: {data['duration']:.1f}秒")
                logger.info(f"📊 流量统计: RTVC={data['traffic']['bytes_to_rtvc']}, MVP={data['traffic']['bytes_to_mvp']}")
                logger.info(f"🔗 连接状态: MVP={data['connections']['mvp_connected']}, RTVC={data['connections']['rtvc_connected']}")
                return True
            else:
                logger.error(f"❌ 会话信息获取失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 会话信息异常: {e}")
            return False
    
    async def test_list_sessions(self) -> bool:
        """测试获取会话列表"""
        logger.info("📋 测试会话列表...")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/sessions")
                
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ 活跃会话: {data['active_sessions']}")
                logger.info(f"📊 总计会话: {data['total_sessions']}")
                
                if data['sessions']:
                    logger.info("📋 会话列表:")
                    for session in data['sessions']:
                        logger.info(f"  - {session['session_id'][:8]}... "
                                  f"状态={session['state']} "
                                  f"电话={session.get('phone_number', 'N/A')}")
                return True
            else:
                logger.error(f"❌ 会话列表获取失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 会话列表异常: {e}")
            return False
    
    async def test_stop_bridge(self, call_uuid: str) -> bool:
        """测试停止桥接会话"""
        logger.info(f"🛑 测试停止桥接: {call_uuid}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/bridge/stop",
                    params={"call_uuid": call_uuid}
                )
                
            if response.status_code == 200:
                data = response.json()
                if data['success']:
                    logger.info(f"✅ 桥接停止成功: {data['message']}")
                    return True
                else:
                    logger.error(f"❌ 桥接停止失败: {data['message']}")
                    return False
            else:
                logger.error(f"❌ 桥接停止请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 桥接停止异常: {e}")
            return False
    
    async def test_service_stats(self) -> bool:
        """测试服务统计信息"""
        logger.info("📊 测试服务统计...")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/stats")
                
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ 服务状态: {data['service']['status']}")
                logger.info(f"📊 会话统计: 活跃={data['sessions']['active']}, 总计={data['sessions']['total']}")
                logger.info(f"🌐 总流量: {data['traffic']['total_bytes']} 字节")
                logger.info(f"🔊 音频配置: {data['audio_config']['freeswitch_sample_rate']}Hz -> {data['audio_config']['rtvc_sample_rate']}Hz")
                return True
            else:
                logger.error(f"❌ 服务统计获取失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 服务统计异常: {e}")
            return False
    
    async def run_full_test(self):
        """运行完整测试套件"""
        logger.info("🧪 开始桥接服务完整测试")
        logger.info("=" * 60)
        
        test_results = []
        
        # 1. 基础服务测试
        logger.info("\n📋 阶段1: 基础服务测试")
        test_results.append(("服务信息", await self.test_service_info()))
        test_results.append(("健康检查", await self.test_health_check()))
        test_results.append(("会话列表", await self.test_list_sessions()))
        test_results.append(("服务统计", await self.test_service_stats()))
        
        # 2. 桥接会话测试
        logger.info("\n📋 阶段2: 桥接会话测试")
        test_call_uuid = str(uuid.uuid4())
        session_id = await self.test_start_bridge(test_call_uuid, "test-1001")
        
        if session_id:
            test_results.append(("启动桥接", True))
            
            # 等待一下让连接建立
            logger.info("⏳ 等待连接建立...")
            await asyncio.sleep(2)
            
            test_results.append(("会话信息", await self.test_session_info(session_id)))
            test_results.append(("停止桥接", await self.test_stop_bridge(test_call_uuid)))
        else:
            test_results.append(("启动桥接", False))
        
        # 3. 最终统计
        logger.info("\n📋 阶段3: 测试后统计")
        test_results.append(("最终统计", await self.test_service_stats()))
        
        # 输出测试结果
        logger.info("\n" + "=" * 60)
        logger.info("🧪 测试结果汇总")
        logger.info("=" * 60)
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"{status} {test_name}")
            if result:
                passed += 1
        
        logger.info("=" * 60)
        logger.info(f"🏆 测试完成: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
        
        return passed == total

async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="音频桥接服务测试")
    parser.add_argument("--host", default="localhost", help="桥接服务主机")
    parser.add_argument("--port", type=int, default=8082, help="桥接服务端口")
    
    args = parser.parse_args()
    
    tester = BridgeServiceTester(args.host, args.port)
    
    try:
        success = await tester.run_full_test()
        if success:
            logger.info("🎉 所有测试通过！")
            return 0
        else:
            logger.error("💥 部分测试失败！")
            return 1
            
    except KeyboardInterrupt:
        logger.info("⚠️  测试被用户中断")
        return 1
    except Exception as e:
        logger.error(f"💥 测试过程中发生异常: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
