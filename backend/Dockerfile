FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 워커가 host의 docker 데몬에 떠 있는 docling 컨테이너를 그대로 실행하기 위한 CLI만 받는다 (데몬은 불필요)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.3.1.tgz \
       | tar xz --strip-components=1 -C /usr/local/bin docker/docker \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

EXPOSE 8000

# 이미 적용된 마이그레이션은 건너뛰니까 매번 떠도 안전하다
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
