#!/bin/bash

echo "🔄 重启 FreeSWITCH 和 MVP 应用..."

# 停止现有容器
echo "⏹️  停止现有容器..."
docker compose down

# 重新构建镜像
echo "🔨 重新构建镜像..."
docker compose build --no-cache

# 启动容器
echo "🚀 启动容器..."
docker compose up -d

# 等待容器启动
echo "⏳ 等待容器启动..."
sleep 10

# 显示容器状态
echo "📊 容器状态:"
docker compose ps

# 显示日志
echo "📝 显示日志 (按 Ctrl+C 退出):"
docker compose logs -f
