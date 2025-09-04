# syntax=docker/dockerfile:1.7-labs
# Dockerfile
ARG DEBIAN_VERSION=bookworm
FROM debian:${DEBIAN_VERSION}

# 构建参数：SignalWire PAT（官方 Debian 包仓库需要认证）
ARG TOKEN

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=en_US.utf8

# 1) 清理所有已有 apt 源（含 .sources），禁用 HTTPS 校验以便直接拉取（不安全）
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt/lists,sharing=locked set -eux; \
    printf 'Acquire::https::Verify-Peer "false";\nAcquire::https::Verify-Host "false";\n' > /etc/apt/apt.conf.d/99insecure; \
    rm -f /etc/apt/sources.list /etc/apt/sources.list.d/* || true; \
    rm -f /etc/apt/sources.list.d/*.sources || true; \
    printf 'deb [trusted=yes] https://deb.debian.org/debian bookworm main\n' > /etc/apt/sources.list; \
    printf 'deb [trusted=yes] https://deb.debian.org/debian bookworm-updates main\n' >> /etc/apt/sources.list; \
    printf 'deb [trusted=yes] https://deb.debian.org/debian-security bookworm-security main\n' >> /etc/apt/sources.list; \
    apt-get update -qq; \
    apt-get install -y --no-install-recommends --no-install-suggests \
      ca-certificates gnupg gosu locales wget curl git \
      build-essential cmake pkg-config ccache \
      libssl-dev zlib1g-dev libevent-dev libspeexdsp-dev; \
    localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

# 2) 添加 SignalWire FreeSWITCH APT 源，使用 TOKEN 认证，安装 FreeSWITCH（vanilla 更轻量）
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt/lists,sharing=locked set -eux; \
    wget --no-verbose --no-check-certificate --http-user=signalwire --http-password=${TOKEN} \
      -O /usr/share/keyrings/signalwire-freeswitch-repo.gpg \
      https://freeswitch.signalwire.com/repo/deb/debian-release/signalwire-freeswitch-repo.gpg; \
    printf 'machine freeswitch.signalwire.com login signalwire password %s\n' "${TOKEN}" > /etc/apt/auth.conf; \
    printf 'deb [signed-by=/usr/share/keyrings/signalwire-freeswitch-repo.gpg] https://freeswitch.signalwire.com/repo/deb/debian-release/ bookworm main\n' > /etc/apt/sources.list.d/freeswitch.list; \
    apt-get -qq update; \
    apt-get install -y --no-install-recommends --no-install-suggests freeswitch-meta-vanilla libfreeswitch-dev

# 3) 编译并安装 mod_audio_stream
RUN --mount=type=cache,target=/root/.cache/ccache set -eux; \
    git clone --depth=1 https://github.com/amigniter/mod_audio_stream.git /usr/src/mod_audio_stream; \
    cd /usr/src/mod_audio_stream; \
    git submodule update --init --depth 1 || git submodule update --init; \
    mkdir -p build; cd build; \
    export CCACHE_DIR=/root/.cache/ccache; ccache -M 1024M || true; \
    cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache ..; \
    make -j"$(nproc)"; \
    make install; \
    rm -rf /usr/src/mod_audio_stream

# 4) 启用模块并设置权限（容器挂载本地 conf 时，以挂载配置为准）
RUN set -eux; \
    sed -i 's#</modules>#  <load module="mod_audio_stream"/>\n</modules>#' /etc/freeswitch/autoload_configs/modules.conf.xml || true; \
    chown -R freeswitch:freeswitch /etc/freeswitch /var/{log,run,lib}/freeswitch || true

# 6) 暴露端口
EXPOSE 8021/tcp \
        5060/tcp 5060/udp 5061/tcp 5061/udp 5080/tcp 5080/udp 5081/tcp 5081/udp \
        5066/tcp 7443/tcp 8081/tcp 8082/tcp \
        16384-16484/udp

# 7) 以前台模式启动
CMD ["/usr/bin/freeswitch","-u","freeswitch","-g","freeswitch","-nonat","-nf"]