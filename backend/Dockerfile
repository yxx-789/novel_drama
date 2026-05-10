FROM python:3.12-slim as builder

WORKDIR /app

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装 Python 依赖
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# 第二阶段：生产镜像
FROM python:3.12-slim

WORKDIR /app

# 安装运行时依赖 + supervisor（同时管理 FastAPI 和 Celery Worker）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制已安装的依赖
COPY --from=builder /root/.local /root/.local

# 确保使用本地安装的包
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 复制应用代码
COPY . .

# 暴露端口（Railway 使用 PORT 环境变量）
EXPOSE 8000

# 复制 supervisor 配置
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 生产环境：先执行数据库迁移，然后启动 supervisor（同时管理 FastAPI + Celery Worker）
CMD bash -c "alembic upgrade head && /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf"
