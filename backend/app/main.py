import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api import documents

app = FastAPI(title="이어봄 API", version="0.1.0")

origins = [origin.strip() for origin in os.environ.get("CORS_ALLOW_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api/v1")


class Health(BaseModel):
    status: str


# 컨테이너 헬스체크용이라 /api/v1 밑에 두지 않는다
@app.get("/health", response_model=Health, tags=["health"])
def health() -> Health:
    return Health(status="ok")
