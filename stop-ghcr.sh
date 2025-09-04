#!/bin/bash

# Free Switch Bot - GHCR 镜像停止脚本

set -e

echo "🛑 Free Switch Bot - 停止 GHCR 服务"
echo "=================================="

# 检查服务是否运行
if docker-compose -f docker-compose.ghcr.yml ps | grep -q "Up"; then
    echo "🔍 发现运行中的服务，正在停止..."
    
    # 停止服务
    docker-compose -f docker-compose.ghcr.yml down
    
    echo "✅ 服务已停止"
    
    # 可选：清理未使用的镜像和容器
    read -p "🧹 是否清理未使用的Docker资源？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🧹 清理未使用的资源..."
        docker system prune -f
        echo "✅ 清理完成"
    fi
else
    echo "ℹ️  没有发现运行中的服务"
fi

echo ""
echo "📋 其他可用命令:"
echo "  - 查看所有容器: docker ps -a"
echo "  - 清理所有停止的容器: docker container prune -f"
echo "  - 清理未使用的镜像: docker image prune -f"
echo "  - 完全清理: docker system prune -a -f"
