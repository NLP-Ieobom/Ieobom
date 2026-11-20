# 이어봄 (Ieobom)

강의자료 PDF를 올리면 슬라이드마다 탐구할 만한 질문을 만들어 주고, 그 질문이 어떤 과목으로
이어지는지, 관련 연구는 어디까지 와 있는지를 같이 보여 주는 학습 도구.

숭실대 AI소프트웨어학부 교육과정을 기준으로 한다. 2025-2학기 자연언어처리 팀 프로젝트.

> **`making_question` 브랜치**는 탐구 질문 생성, 연구 동향, 후속 학습 방향(이어서 볼 과목)을 맡는다.
> 프런트 연결은 [필요한 API 2개](#프런트에서-호출할-api-2개)와 [화면에 넣을 결과 JSON](#화면에-넣을-결과-json)부터 확인하면 된다.

## 프런트에서 호출할 API 2개

PDF 뷰어의 문서 ID와 **원본 PDF 쪽 번호(1부터 시작)**를 사용한다. 두 API에 기존 로그인 토큰을 `Authorization: Bearer <access_token>`으로 보낸다.

| 언제 호출하나 | API | 응답 |
| --- | --- | --- |
| 슬라이드를 열거나 쪽을 바꿀 때 | `GET /api/v1/documents/{document_id}/pages/{page_number}/learning` | 해당 쪽의 저장된 분석·발견 질문·근거 좌표. **더 깊이 알아보기**도 여기서 받은 질문 데이터를 사용한다. |
| 학생이 추가 질문을 보낼 때 | `POST /api/v1/documents/{document_id}/pages/{page_number}/ask` | Gemini가 만든 답변과 해당 쪽의 근거 블록 ID. |

추가 질문의 요청 본문은 `{"question":"정규화하면 조회 비용도 항상 줄어드나요?"}`이고, 응답은 아래 형식이다. 프런트는 이 근거 ID를 이미 받아둔 쪽의 좌표에 연결할 수 있다.

```json
{
  "explanation": "갱신 이상은 줄어들지만, 조회에 조인이 추가될 수 있습니다.",
  "evidence_block_ids": ["p2-b2"]
}
```

첫 조회가 분석 완료 전에 이루어지면 404가 올 수 있으므로 기존 문서 상태 API(`GET /api/v1/documents/{document_id}/status`)를 함께 사용한다. 표지처럼 제외된 쪽은 조회 결과의 `analysis.question_eligible`이 `false`이고 `questions`가 비어 있다. 이런 쪽에서는 추가 질문 버튼을 비활성화한다.

## 화면에 넣을 결과 JSON

프런트 개발 중에는 [실제 생성 예시 JSON](docs/examples/learning.example.json)에서 **`pages["2"]`**를 읽어 테스트할 수 있다. 이 객체가 **GET `/learning` 한 건의 응답**과 같은 구조다. 같은 예시 파일의 `follow_up`에는 추가 질문의 응답 필드와 함께 시험에 쓴 `page_number`, `question`이 들어 있다.

| 구현한 기능 | 프런트가 읽을 필드 |
| --- | --- |
| **슬라이드 옆 발견 질문** | `questions[].question`, `type`, `why_recommended`로 카드 표시 |
| **슬라이드 위 물음표와 근거 표시** | 선택한 질문의 `evidence_block_ids`를 이 쪽 `evidence_blocks[].block_id`와 매칭. 첫 근거 블록 옆에 물음표를 놓고 클릭하면 근거 블록 전체를 강조한다. `bbox`는 좌상단 기준 0~1 좌표 `[left, top, right, bottom]`이다. |
| **더 깊이 알아보기** | 선택한 질문의 `explanation.headline`, `body`, `flow`로 해설 표시. `prerequisites`, `learning_steps`, `first_activity`로 선행 개념·학습 순서·첫 활동 표시 |
| **이어서 볼 과목** | 선택한 질문의 `related_courses[]`에서 과목명·추천 이유·다음 주제 표시. `relation`으로 앞 학기(`previous`)와 뒤 학기(`next`)를 구분한다. 편성 학기가 확인되지 않으면 `related`가 반환되며, `source`로 AI 추천임을 표시한다. |
| **연구 동향** | 선택한 질문의 `trends[]`에서 제목·요약·링크 표시. `source: "semantic_scholar"`는 논문 검색 결과, `source: "gemini"`는 AI가 정리한 연구 방향으로 표시한다. |
| **추가 질문 답변** | POST 응답의 `explanation`과 `evidence_block_ids`로 답변과 원문 근거 표시 |

과목 추천과 연구 동향은 **질문마다** 달라서 `questions[]` 안에 있다. 관련 결과가 없으면 빈 배열이 반환된다. 쪽의 `research_status`로 기능이 꺼졌는지(`disabled`), 준비됐는지(`ready`), 조회에 실패했는지(`unavailable`)를 구분한다. [전체 필드와 예시](docs/learning-output.md)

## 왜 만드나

수업에서 개념은 이해했는데 "그래서 뭘 더 찾아봐야 하지"에서 막히는 경우가 많다.
모르는 걸 묻는 건 할 수 있어도, 아직 접하지 못한 응용이나 개념 사이의 관계는
무엇을 물어야 할지조차 모른다. 요약이나 QA 서비스로는 이 부분이 해결되지 않는다.

그래서 질문을 학생이 떠올리기를 기다리는 대신, 자료와 교육과정을 미리 분석해서
질문 후보와 학습 순서를 먼저 깔아 둔다. 학생은 PDF를 읽다가 옆에 뜬 질문을 보고,
더 궁금하면 그 자리에서 묻는다.

## 어떻게 동작하나

PDF를 업로드하면 그 시점에 분석이 한 번 돈다. Docling으로 페이지 구조를 뽑고,
Gemini로 개념과 요약을 추출한 다음, 슬라이드마다 질문 두세 개와 연결되는 후속 과목을 만든다.
과목에 동향 기능이 켜져 있으면 Semantic Scholar에서 관련 논문도 찾아 요약해 둔다.

학생이 읽을 때는 저장된 결과를 그대로 보여 준다. AI를 다시 부르는 건 학생이 직접
질문을 던질 때뿐이다. 분석은 수십 초에서 몇 분 걸리니까 비동기로 돌리고, 학생은 진행
상태만 본다. 화면을 떠나도 분석은 계속된다.

질문은 아래 다섯 가지 관점에서 만든다. 슬라이드가 어디까지 설명하느냐에 따라
맞는 것만 골라 쓴다. 다섯 개를 다 채우지 않는다.

| 관점 | 예시 |
| --- | --- |
| 이전 내용과 연결하기 | MapReduce의 장애 복구와 Spark의 RDD Lineage는 어떤 관계일까 |
| 전체 흐름에서 이해하기 | MapReduce 다음에 Spark를 배우는 이유는 무엇일까 |
| 당연한 내용 의심하기 | Spark는 메모리를 쓰니까 언제나 더 빠를까 |
| 실제 상황에 적용하기 | 데이터가 메모리보다 크면 어떤 설정을 골라야 할까 |
| 강의 밖으로 확장하기 | 최근 시스템들은 Spark의 어떤 한계를 개선하려 할까 |

## 구성

```
backend/   FastAPI 서버와 분석 워커 (Python)
frontend/  React + TypeScript (Vercel 배포)
infra/     Docker, Nginx 설정
docs/      설계 문서
```

서버와 워커는 같은 코드를 공유하고 진입점만 다르다. 둘은 서로를 호출하지 않고
PostgreSQL의 잡 테이블로만 주고받는다. 구조와 파이프라인은 [docs/architecture.md](docs/architecture.md),
기술 선택 이유와 아직 정하지 못한 것들은 [docs/decisions.md](docs/decisions.md)에 적었다.

## 현재 상태

이 브랜치에 페이지별 학습 결과 생성과 조회, 학생의 추가 질문 API가 구현돼 있다.
프런트 연동에 사용할 API와 예시 응답은 위 섹션에서 확인할 수 있다.

## 환경 변수

`.env.example`을 복사해 `.env`를 만들고 값을 채운다. 키는 커밋하지 않는다.

```bash
cp .env.example .env
```

## 이 브랜치의 코드 구성과 입출력

Docling 추출 결과를 받아 쪽마다 분석, 탐구 질문, 질문의 근거 블록 ID, 더 알아보기 내용(해설·이어서 볼 과목·연구 동향)을 담은 학습 결과 JSON을 만든다. 서버는 이 JSON을 문서마다 저장하고 쪽 단위로 내준다. 결과 JSON의 필드는 [docs/learning-output.md](docs/learning-output.md)에, 실행 설정과 테스트 방법은 [docs/learning.md](docs/learning.md)에 자세히 적었다.

### 입력과 출력

| 구분 | 형식 | 오는 곳 / 가는 곳 |
| --- | --- | --- |
| 입력 | 팀 공통 추출 v1 JSON. `schema_version: "1.0"`, 좌상단 기준 정규화 좌표, 쪽마다 `blocks[]`(`block_id`, `kind`, `text`, `bbox`, 표) | 워커가 Docling 결과를 변환해 `document_learning.extraction`에 저장 |
| 출력 | 학습 결과 JSON. `pages["쪽 번호"]`마다 `analysis`, `questions[]`(질문, `evidence_block_ids`, 해설, 이어서 볼 과목, 연구 동향), `evidence_blocks[]`(블록 좌표) | `document_learning.result`에 저장하고 API가 쪽 단위로 반환 |
| 추가 질문 | 쪽 번호와 학생의 질문 | 답변과 근거 블록 ID. 저장하지 않고 바로 응답 |

### 서버 처리 흐름

```text
PDF 업로드 → analysis_job 등록
  → 워커 (app/worker/run.py)
      1. S3에서 PDF를 받아 Docling 실행
      2. docling_output.load_docling_extraction()         → 추출 v1 JSON  → document_learning.extraction
      3. learning.generate_learning(db, gemini, course, …) → 학습 결과 JSON → document_learning.result
  → API (app/api/documents.py)
      GET  /api/v1/documents/{document_id}/pages/{page_number}/learning   저장된 쪽 결과 반환 (Gemini 호출 없음)
      POST /api/v1/documents/{document_id}/pages/{page_number}/ask        answer_follow_up()으로 Gemini 호출
```

`GEMINI_API_KEY`가 없으면 2단계까지만 저장하고, 키를 넣은 뒤 결과를 채울 수 있다. Gemini의 일시적 오류는 잡 단위로 최대 세 번 다시 시도한다. 두 API 모두 문서 소유권을 확인하고, 결과가 없거나 다른 사용자의 문서면 404를 반환한다.

### 파일별 역할

| 파일 | 역할 | 입력 → 출력 |
| --- | --- | --- |
| `app/pipelines/learning.py` | 생성의 핵심. 쪽 분석, 질문·해설 생성, 과목·논문 선택, 결과 검증 | `generate_learning`: 추출 v1 dict → 학습 결과 dict<br>`answer_follow_up`: 쪽과 학생 질문 → 답변 |
| `app/pipelines/learning_cli.py` | DB 없이 실행하는 명령줄. 과목 검색을 pgvector와 같은 계산으로 메모리에서 한다 | 추출 JSON 파일 → 학습 결과 JSON 파일 |
| `app/pipelines/docling_output.py` | 워커가 받은 Docling 출력을 추출 v1 형식으로 변환 | Docling 출력 폴더 → 추출 v1 dict |
| `app/services/curriculum_search.py` | 교육과정 ZIP 인덱싱(`import_catalog`), 과목 후보 검색(`find_candidates`) | ZIP → `course_learning_profile`<br>쪽 벡터 → 앞 학기·뒤 학기 과목 후보 |
| `app/services/research.py` | 연구 동향(`course_trends`). Semantic Scholar 검색, 초록 요약, 검색 실패 시 Gemini 연구 방향 | 과목 → 논문 요약 목록(30일 캐시) |
| `app/integrations/gemini.py` | Gemini 텍스트 생성(응답 JSON 스키마 지정)과 임베딩 | 지시문·데이터·스키마 → 검증된 객체 |
| `app/integrations/semantic_scholar.py`, `learning_http.py` | 논문 검색, 외부 API 호출과 재시도 가능 여부 판단 | 검색어 → 최근 5년 논문 |
| `app/schemas/learning.py` | 학습 결과 JSON의 Pydantic 스키마(`PageLearning`, `QuestionLearning` 등) | API 응답 모델과 생성 결과 검증에 같이 쓴다 |
| `app/models/learning.py` | 아래 DB 테이블 세 개 | |
| `app/api/documents.py` | 위 learning·ask 경로 | |
| `app/worker/run.py` | 업로드 후 추출과 생성 | |
| `migrations/versions/c4ab0f5b3168`, `5d2e7a1c9b40` | 테이블 생성, 과목 편성 학기 컬럼 추가 | |
| `tests/test_learning.py`, `test_learning_cli.py` | 회귀 테스트 12개. API 키 없이 실행 | |

### DB 테이블

| 테이블 | 기본 키 | 내용 |
| --- | --- | --- |
| `document_learning` | `document_id` | `extraction`(추출 v1, JSONB), `result`(학습 결과 JSON, JSONB) |
| `course_learning_profile` | `course_id` | 교육과정 과목의 계획서 주제, 편성 학기(`semester_order`, 3학년 2학기는 32), 임베딩(vector 1536) |
| `course_research_cache` | `course_id` | 과목별 논문 요약과 검색 시점. 30일 동안 재사용 |

### 외부 API를 부르는 시점

| 시점 | 호출 |
| --- | --- |
| 문서 분석(업로드마다 한 번) | Gemini 텍스트: 3쪽마다 분석·질문 생성 1번, 과목·논문 선택 1번<br>Gemini 임베딩: 질문을 만든 쪽의 요약마다 1개 |
| 교육과정 인덱싱(한 번) | Gemini 임베딩: 과목 수만큼 |
| 연구 동향(과목마다 30일에 한 번) | Gemini로 검색어와 요약, Semantic Scholar 검색 2~3번 |
| 추가 질문(요청마다) | Gemini 텍스트 1번 |
| 결과 조회 | 없음 |

### 환경 변수

| 변수 | 쓰는 곳 | 비고 |
| --- | --- | --- |
| `GEMINI_API_KEY` | 워커, 추가 질문 API | 없으면 추출만 저장하고 추가 질문은 503 |
| `GEMINI_TEXT_MODEL` | 텍스트 생성 | 기본값 `gemini-2.5-flash`는 새로 발급한 키에서 404를 반환한다. 쓸 수 있는 모델로 바꾼다 |
| `GEMINI_EMBEDDING_MODEL` | 임베딩 | 바꾸면 교육과정을 다시 인덱싱한다 |
| `SEMANTIC_SCHOLAR_API_KEY` | 연구 동향 | 없으면 공용 한도라 429가 잦다 |
| `SEMANTIC_SCHOLAR_TIMEOUT` | 연구 동향 | 기본 20초 |
| `GEMINI_FALLBACK_MODELS` | 명령줄 생성기만 | 과부하 때 번갈아 쓸 모델(쉼표로 구분) |

### 바로 실행해 보기

```bash
cd backend
python -m unittest discover -s tests -v          # 키 없이 회귀 테스트 12개
python -m app.pipelines.learning_cli extraction.json -o learning.json --env-file ../.env \
  --corpus ieobom-ssu-corpus.zip --course-code 21501666 --trends   # 추출 JSON → 학습 결과 JSON
```

팀 예시 입력으로 실제 생성한 결과는 [docs/examples/learning.example.json](docs/examples/learning.example.json)에 있다.

### main에 합칠 때 할 일

- **워커 연결**: main 워커는 `pdf_extraction` 추출기로 같은 추출 v1 JSON을 만들고, `document_analysis.analyze_document(extraction)`는 아직 빈 결과를 돌려준다. 그 자리에서 `generate_learning`을 부르고 결과를 `document_learning.result`에 저장하면 된다. 이 브랜치의 `docling_output.py` 변환은 main 추출기로 대체할 수 있다.
- **API**: `app/api/documents.py`는 양쪽에서 모두 수정했다. 이 브랜치의 learning·ask 경로 두 개를 main 파일로 옮긴다.
- **마이그레이션**: 이 브랜치의 Alembic 경로(`c4ab0f5b3168` → `5d2e7a1c9b40`)와 main의 head를 하나로 잇고, `migrations/env.py`에 learning 모델을 등록한다.
- **질문 저장과 연결**: main의 `question` 테이블에는 해설·근거 블록 ID·이어서 볼 과목·연구 동향 컬럼이 없다. 저장 버튼(`is_saved`)과 원문 표시가 같은 질문을 가리키려면 생성 질문을 main 질문 ID에 연결하거나 컬럼을 추가한다.
- **교육과정 인덱싱**: 편성 학기를 함께 저장하도록 `python -m app.services.curriculum_search ieobom-ssu-corpus.zip`을 한 번 실행한다.
