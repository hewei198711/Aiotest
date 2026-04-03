# AioTest Dockerfile

# 第一阶段：构建环境
FROM python:3.12-slim AS builder

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*  # 清理apt缓存，减少镜像大小

# 创建虚拟环境, 并设置虚拟环境路径
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制运行时依赖文件,升级pip并安装依赖
COPY requirements.txt /build/requirements.txt
RUN python3 -m pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r /build/requirements.txt  # --no-cache-dir 减少镜像大小

# 第二阶段：运行环境
FROM python:3.12-slim

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 设置环境变量,加入虚拟环境路径
ENV PATH="/opt/venv/bin:$PATH"
# 禁用Python缓冲，确保日志实时输出
ENV PYTHONUNBUFFERED=1

# 创建非root用户
RUN useradd -m -u 1000 aiotest  # 创建用户aiotest，UID为1000

# 设置工作目录
WORKDIR /app

# 更改目录所有权
RUN chown -R aiotest:aiotest /app

# 切换到非root用户
USER aiotest

# 复制应用代码
COPY . /app

# 暴露 Prometheus指标，Web控制界面端口
EXPOSE 8089

