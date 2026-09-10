# 后端镜像
FROM python:3.12-slim

WORKDIR /app

# 先装依赖以利用缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY src ./src
COPY .env.example .env.example

EXPOSE 8000

# 默认以 Mock LLM 启动后端（无需 API Key 即可演示）
ENV LLM_PROVIDER=mock

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
