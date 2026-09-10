# ============ 多阶段构建：builder 安装依赖，runtime 只保留运行所需 ============
FROM python:3.12-slim AS builder

WORKDIR /app

# 先复制依赖清单以利用 Docker 层缓存
COPY requirements.txt .

# 安装到独立 venv，避免污染系统 site-packages
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ============ 运行时镜像：精简，不含编译工具与 pip 缓存 ============
FROM python:3.12-slim

WORKDIR /app

# 直接复用 builder 阶段的 venv
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制源码与配置模板
COPY src ./src
COPY eval ./eval
COPY alembic ./alembic
COPY alembic.ini .
COPY .env.example .env.example

# 数据目录（SQLite 持久化卷挂载点）
RUN mkdir -p /app/data
VOLUME /app/data

EXPOSE 8000

# 默认以 Mock LLM 启动后端（无需 API Key 即可演示）
ENV LLM_PROVIDER=mock \
    DATABASE_URL=sqlite:////app/data/cyber_foodie.db

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
