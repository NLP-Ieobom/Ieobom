# 탐구 질문 실행과 main 통합

## 코드 위치

| 위치 | 역할 |
| --- | --- |
| `backend/app/pipelines/learning.py` | 추출 JSON → 쪽별 질문·원문 근거·해설·학습 경로 |
| `backend/app/pipelines/learning_cli.py` | JSON 파일로 위 과정을 실행하는 명령줄 |
| `backend/app/services/curriculum_search.py`, `research.py` | 과목 후보 검색, 연구 동향 조회·캐시 |
| `backend/app/worker/run.py`, `backend/app/api/documents.py` | 결과를 `document_learning.result`에 저장하고 쪽별 조회·추가 질문에 사용 |

## 빠른 검증

백엔드 의존성을 설치한 뒤 `backend/`에서 실행한다. 실제 생성에는 `../.env`에 `GEMINI_API_KEY`와 사용 가능한 `GEMINI_TEXT_MODEL`이 필요하다.

```bash
python -m unittest discover -s tests -v
python -m app.pipelines.learning_cli extraction.json -o learning.json --env-file ../.env
```

추천 과목도 보려면 `--corpus ieobom-ssu-corpus.zip --course-code 21501666`, 연구 동향은 `--trends`, 추가 답변은 `--page 2 --ask "정규화하면 조회 비용도 항상 줄어드나요?"`를 추가한다. Semantic Scholar 키가 있으면 `SEMANTIC_SCHOLAR_API_KEY`에 설정한다. [출력 예시](examples/learning.example.json)

## main에 합칠 때

1. main 워커의 추출 v1 JSON을 `generate_learning()`에 넘기고, 결과를 `document_learning.result`에 저장한다.
2. [README의 API 두 개](../README.md#프런트에서-호출할-api-2개)를 추가하고, 발견 질문을 main의 질문 ID와 연결해 원문 강조와 저장 버튼이 같은 질문을 가리키게 한다.
3. Alembic 리비전 `c4ab0f5b3168` → `5d2e7a1c9b40`을 main 마이그레이션과 연결하고 `migrations/env.py`에 모델을 등록한다.
4. 서비스 DB에서 `python -m app.services.curriculum_search ieobom-ssu-corpus.zip`으로 과목과 편성 학기를 인덱싱한다. 테스트 PDF 한 건으로 업로드부터 질문 조회와 저장까지 확인한다.
