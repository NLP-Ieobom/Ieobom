import json
import math
import os
import time
from typing import TypeVar

from pydantic import BaseModel

from app.integrations.learning_http import ProviderError, request_json

T = TypeVar("T", bound=BaseModel)
EMBEDDING_DIM = 1536
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
# 사고 토큰은 출력으로 과금되고 캐시된 입력은 단가가 다르다. 원가를 계산하려면 네 개가 다 필요하다.
USAGE_FIELDS = ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount", "cachedContentTokenCount")


class Gemini:
    def __init__(self, tags: dict | None = None, sink=None):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ProviderError("GEMINI_API_KEY is required", retryable=False)
        self.headers = {"x-goog-api-key": api_key}
        # 잡 하나가 인스턴스 하나를 쓰니 문서·잡 ID를 여기 담아 두면 호출마다 다시 넘기지 않아도 된다
        self.tags = tags or {}
        # DB에 기록할 때만 넘긴다. CLI와 테스트는 DB가 없어서 로그 한 줄로 끝난다.
        self.sink = sink
        self.text_model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash").removeprefix("models/")
        self.embedding_model = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").removeprefix("models/")

    def _log_usage(self, response: dict, *, call: str, model: str, attempt: int, started: float) -> None:
        usage = response.get("usageMetadata") or {}
        elapsed_ms = round((time.monotonic() - started) * 1000)
        print(json.dumps({
            "event": "gemini_usage", **self.tags, "call": call, "model": model, "attempt": attempt,
            "elapsed_ms": elapsed_ms,
            **{field: usage[field] for field in USAGE_FIELDS if field in usage},
        }, ensure_ascii=False), flush=True)
        if self.sink is not None:
            self.sink(call=call, model=model, attempt=attempt, elapsed_ms=elapsed_ms, usage=usage)

    def generate(self, instructions: str, data: dict, schema: type[T], *, call: str, attempt: int = 1) -> T:
        payload = {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [{"parts": [{"text": json.dumps(data, ensure_ascii=False)}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema.model_json_schema(),
                "temperature": 0.2,
                # 3쪽 묶음의 질문별 단락형 해설과 사고 토큰이 함께 들어가도록 여유를 둔다
                "maxOutputTokens": 32768,
            },
        }
        started = time.monotonic()
        response = request_json(
            f"{BASE_URL}/models/{self.text_model}:generateContent",
            provider="Gemini",
            headers=self.headers,
            payload=payload,
            timeout=90,
        )
        # 검증에 걸려 버리는 응답도 토큰을 쓴 것이라 파싱 전에 남긴다
        self._log_usage(response, call=call, model=self.text_model, attempt=attempt, started=started)
        try:
            candidate = response["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ValueError("Unfinished response")
            raw = "".join(
                part["text"] for part in candidate["content"]["parts"]
                if "text" in part and not part.get("thought")
            )
            return schema.model_validate_json(raw)
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("Gemini returned invalid structured output") from None

    def embed(self, texts: list[str], task: str, *, call: str) -> list[list[float]]:
        if not texts:
            return []
        model = f"models/{self.embedding_model}"
        started = time.monotonic()
        response = request_json(
            f"{BASE_URL}/{model}:batchEmbedContents",
            provider="Gemini",
            headers=self.headers,
            payload={"requests": [
                {
                    "model": model,
                    "content": {"parts": [{"text": text}]},
                    "taskType": task,
                    "outputDimensionality": EMBEDDING_DIM,
                }
                for text in texts
            ]},
            timeout=90,
        )
        # batchEmbedContents가 usageMetadata를 주는지 실제 응답으로 확인하지 못했다. 없으면 토큰 필드만 빠진다.
        self._log_usage(response, call=call, model=self.embedding_model, attempt=1, started=started)
        try:
            vectors = [item["values"] for item in response["embeddings"]]
            if len(vectors) != len(texts) or any(
                len(vector) != EMBEDDING_DIM
                or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector)
                or not any(vector)
                for vector in vectors
            ):
                raise ValueError("Invalid embedding dimensions or values")
            return vectors
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ProviderError("Gemini returned invalid embeddings") from None
