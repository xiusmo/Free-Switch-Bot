#!/bin/bash

# FreeSWITCH AI 音频流处理系统启动脚本

set -e

echo "🚀 启动 FreeSWITCH AI 音频流处理系统..."
echo "=========================================="

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未运行，请先启动 Docker"
    exit 1
fi

# 检查 docker-compose 是否可用
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose 未安装，请先安装 docker-compose"
    exit 1
fi

# 检查配置文件
if [ ! -f "../.env" ]; then
    echo "⚠️  未找到 .env 文件，使用默认配置"
    echo "   如需自定义配置，请复制 .env.example 为 .env 并修改"
fi

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p ../recordings
mkdir -p ../logs

# 检查示例音频文件
if [ ! -f "wav-example.wav" ]; then
    echo "⚠️  未找到 wav-example.wav 文件"
    echo "   系统将使用静音音频作为默认播放内容"
fi

# 启动服务
echo "🐳 启动 Docker 服务..."
cd ..
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "🔍 检查服务状态..."
if docker-compose ps | grep -q "Up"; then
    echo "✅ 服务启动成功！"
    echo ""
    echo "📊 服务状态："
    docker-compose ps
    echo ""
    echo "🌐 访问地址："
    echo "   - MVP 服务: http://localhost:8080"
    echo "   - 健康检查: http://localhost:8080/health"
    echo "   - API 文档: http://localhost:8080/docs"
    echo ""
    echo "📝 查看日志："
    echo "   docker-compose logs -f mvp"
    echo ""
    echo "🧪 运行测试："
    echo "   cd mvp && python test_system.py"
    echo ""
    echo "🛑 停止服务："
    echo "   docker-compose down"
else
    echo "❌ 服务启动失败"
    echo "查看日志：docker-compose logs"
    exit 1
fi
