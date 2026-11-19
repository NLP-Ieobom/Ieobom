import json
import math
import os
from typing import TypeVar

from pydantic import BaseModel

from app.integrations.learning_http import ProviderError, request_json

T = TypeVar("T", bound=BaseModel)
EMBEDDING_DIM = 1536
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class Gemini:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ProviderError("GEMINI_API_KEY is required", retryable=False)
        self.headers = {"x-goog-api-key": api_key}
        self.text_model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash").removeprefix("models/")
        self.embedding_model = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").removeprefix("models/")

    def generate(self, instructions: str, data: dict, schema: type[T]) -> T:
        payload = {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [{"parts": [{"text": json.dumps(data, ensure_ascii=False)}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema.model_json_schema(),
                "temperature": 0.2,
                "maxOutputTokens": 8192,
            },
        }
        response = request_json(
            f"{BASE_URL}/models/{self.text_model}:generateContent",
            provider="Gemini",
            headers=self.headers,
            payload=payload,
            timeout=90,
        )
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

    def embed(self, texts: list[str], task: str) -> list[list[float]]:
        if not texts:
            return []
        model = f"models/{self.embedding_model}"
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
