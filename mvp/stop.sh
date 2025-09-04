#!/bin/bash

# FreeSWITCH AI 音频流处理系统停止脚本

echo "🛑 停止 FreeSWITCH AI 音频流处理系统..."
echo "========================================"

# 检查 docker-compose 是否可用
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose 未安装"
    exit 1
fi

# 切换到项目根目录
cd ..

# 停止服务
echo "🐳 停止 Docker 服务..."
docker-compose down

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo "❌ 服务停止失败"
    echo "强制停止：docker-compose down --remove-orphans"
    docker-compose down --remove-orphans
else
    echo "✅ 服务已停止"
fi

echo ""
echo "📊 当前 Docker 容器状态："
docker ps -a --filter "name=freeswitch\|fs-mvp" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🧹 清理完成！"
echo "如需重新启动，请运行：cd mvp && ./start.sh"
