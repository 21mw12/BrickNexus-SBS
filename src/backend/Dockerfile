FROM python:3.12-slim

WORKDIR /app

# 先拷贝依赖清单，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝应用代码、迁移脚本与配置
COPY main.py .
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY config.yaml .
COPY resources/ ./resources/

EXPOSE 3033

# 单进程运行：collector / rule / rdf / WebSocket 均为进程内单例，禁止 --workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3033"]
