from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="이어봄 API", version="0.1.0")


class Health(BaseModel):
    status: str


# 컨테이너 헬스체크용이라 /api/v1 밑에 두지 않는다
@app.get("/health", response_model=Health, tags=["health"])
def health() -> Health:
    return Health(status="ok")
