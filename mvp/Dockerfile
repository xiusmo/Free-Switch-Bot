FROM python:3.11-slim

# 安装系统依赖和构建工具
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    build-essential \
    gcc \
    g++ \
    portaudio19-dev \
    rust-all \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制依赖文件
COPY mvp/requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建必要的目录
RUN mkdir -p /app/recordings /app/app

# 复制应用代码
COPY mvp/app ./app

# 复制 RealtimeVoiceChat 代码到容器中
COPY RealtimeVoiceChat ./RealtimeVoiceChat

# 复制示例音频文件
COPY mvp/wav-example.wav ./wav-example.wav

# 设置环境变量
ENV PORT=8080
ENV FS_HOST=freeswitch
ENV FS_PORT=8021
ENV FS_PASSWORD=ClueCon
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 8080

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"] 