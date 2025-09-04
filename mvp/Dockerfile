FROM python:3.11-slim-bookworm

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive

# 配置 APT 源和网络重试
RUN set -eux; \
    # 配置 APT 超时和重试设置
    echo 'Acquire::http::Timeout "300";' > /etc/apt/apt.conf.d/99timeout; \
    echo 'Acquire::https::Timeout "300";' >> /etc/apt/apt.conf.d/99timeout; \
    echo 'Acquire::Retries "5";' >> /etc/apt/apt.conf.d/99timeout; \
    echo 'APT::Get::Assume-Yes "true";' >> /etc/apt/apt.conf.d/99timeout; \
    echo 'APT::Install-Recommends "false";' >> /etc/apt/apt.conf.d/99timeout; \
    echo 'APT::Install-Suggests "false";' >> /etc/apt/apt.conf.d/99timeout; \
    # 清理并设置稳定的 Debian 源（包含备用镜像）
    rm -f /etc/apt/sources.list.d/* || true; \
    { \
        echo 'deb http://deb.debian.org/debian bookworm main'; \
        echo 'deb http://security.debian.org/debian-security bookworm-security main'; \
        echo 'deb http://deb.debian.org/debian bookworm-updates main'; \
        echo '# 备用镜像源'; \
        echo 'deb http://ftp.debian.org/debian bookworm main'; \
        echo 'deb http://ftp.us.debian.org/debian bookworm main'; \
    } > /etc/apt/sources.list; \
    # 尝试更新包列表（带重试逻辑）
    for i in 1 2 3; do \
        apt-get update --fix-missing && break || { \
            echo "尝试 $i/3 失败，等待 5 秒后重试..."; \
            sleep 5; \
        }; \
    done; \
    # 安装系统依赖
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        ca-certificates \
        wget \
        curl \
    ; \
    # 清理缓存
    apt-get autoremove -y; \
    apt-get autoclean; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /tmp/* /var/tmp/*

WORKDIR /app

# 复制依赖文件
COPY mvp/requirements.txt .

# 配置 pip 并安装Python依赖
RUN set -eux; \
    # 配置 pip 镜像源和超时
    pip config set global.timeout 300; \
    pip config set global.retries 5; \
    pip config set global.index-url https://pypi.org/simple/; \
    pip config set global.extra-index-url https://pypi.python.org/simple/; \
    # 升级 pip 和安装依赖
    pip install --no-cache-dir --upgrade pip setuptools wheel; \
    pip install --no-cache-dir -r requirements.txt

# 创建必要的目录
RUN mkdir -p /app/recordings /app/app

# 复制应用代码
COPY mvp/app ./app

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