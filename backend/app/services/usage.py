from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal
from app.models.gemini_usage import GeminiUsage

TOKEN_COLUMNS = {
    "promptTokenCount": "prompt_tokens",
    "candidatesTokenCount": "output_tokens",
    "thoughtsTokenCount": "thought_tokens",
    "cachedContentTokenCount": "cached_tokens",
}


def usage_sink(document_id=None):
    """Gemini에 넘길 기록 함수를 만든다. 단가는 넣지 않고 토큰만 남겨 조회할 때 곱한다."""

    def record(*, call, model, attempt, elapsed_ms, usage) -> None:
        try:
            # 잡 세션에 쓰면 실패한 잡을 롤백할 때 재시도로 쓴 비용 기록이 함께 사라진다
            with SessionLocal() as db:
                db.add(GeminiUsage(
                    document_id=document_id, call=call, model=model, attempt=attempt, elapsed_ms=elapsed_ms,
                    **{column: usage[field] for field, column in TOKEN_COLUMNS.items() if field in usage},
                ))
                db.commit()
        except SQLAlchemyError as error:
            # 측정 기록을 못 남기는 것이 분석이나 답변을 실패시킬 이유는 되지 않는다
            print(f"gemini usage not recorded: {error}", flush=True)

    return record
