# 탐구 질문 결과 JSON 형식

이 문서는 질문 생성 단계가 무엇을 받아서 무엇을 내놓는지 정리한다. 프런트엔드와 백엔드 통합에서 이 결과를 읽을 때 참고한다.

- **입력**: Docling 추출 결과를 팀 공통 추출 v1 형식으로 바꾼 JSON. 형식은 `pdf_extraction` 브랜치의 `docs/extraction/pdf.schema.json`을 따른다.
- **출력**: 쪽마다 분석, 탐구 질문, 질문의 근거 블록 ID, 더 알아보기 내용(해설·이어서 볼 과목·연구 동향)을 담은 JSON. 아래에서 필드별로 설명한다.

실제 출력 예시는 [examples/learning.example.json](examples/learning.example.json)에 있다. 팀 예시 입력 `pdf.example.json`(정규화 2쪽짜리 가상 자료)을 데이터베이스 과목(21501656, 3학년 1학기)으로 넣고 아래 명령으로 생성했다.

```bash
python -m app.pipelines.learning_cli pdf.example.json -o learning.example.json --env-file ../.env \
  --corpus ieobom-ssu-corpus.zip --course-code 21501656 --trends --page 2 --ask "정규화하면 조회 비용도 항상 줄어드나요?"
```

## 만드는 방법

DB, S3, 워커 없이 추출 JSON 하나로 만들 수 있다.

```bash
cd backend
python -m app.pipelines.learning_cli extraction.json -o learning.json --env-file ../.env
```

| 옵션 | 뜻 |
| --- | --- |
| `--course-name 데이터베이스` | 과목명. 질문 생성의 맥락으로 쓴다. `--corpus`를 주면 교육과정의 과목명을 쓴다 |
| `--corpus ieobom-ssu-corpus.zip --course-code 21501666` | 팀 교육과정 ZIP으로 이어서 볼 과목을 찾는다. 해당 과목의 계획서 주제와 편성 학기를 쓴다 |
| `--trends` | Semantic Scholar로 연구 동향을 찾는다. `SEMANTIC_SCHOLAR_API_KEY`가 있으면 한도가 덜 막힌다 |
| `--ask "질문" --page 2` | 그 쪽에 대한 추가 질문 답변도 `follow_up`에 담는다 |

`.env`에는 `GEMINI_API_KEY`가 필요하다. 2026년 11월 기준으로 새로 발급한 키는 `gemini-2.5-flash`를 쓸 수 없으므로 `GEMINI_TEXT_MODEL`에 쓸 수 있는 모델을 넣는다. 이 문서의 예시는 `GEMINI_TEXT_MODEL=gemini-3.1-flash-lite`, `GEMINI_EMBEDDING_MODEL=gemini-embedding-2`로 만들었다. 무료 등급의 임베딩은 모델마다 하루 1,000건으로 제한된다.

서비스에서는 워커가 같은 함수 `app.pipelines.learning.generate_learning(db, gemini, course, extraction)`를 부른다. 그 결과를 `document_learning.result`에 저장하고, API가 쪽 단위로 내준다. 명령줄은 pgvector 대신 같은 계산을 메모리에서 하고, 나머지는 모두 같은 코드를 쓴다.

## 최상위 구조

```json
{
  "schema_version": "1.0",
  "document_id": "demo-normalization",
  "pages": {
    "1": { "...": "쪽 객체" },
    "2": { "...": "쪽 객체" }
  },
  "follow_up": { "...": "--ask를 줬을 때만" }
}
```

| 필드 | 설명 |
| --- | --- |
| `schema_version` | 이 결과 형식의 버전. 현재 `"1.0"` |
| `document_id` | 입력 추출 JSON의 `document_id`. 명령줄 출력에만 있다. 워커는 `document_learning.document_id`에 저장한다 |
| `pages` | 원본 PDF 쪽 번호(1부터)를 문자열 키로 쓴다. 표지처럼 질문을 만들지 않은 쪽도 빠짐없이 들어간다 |
| `follow_up` | `--ask`로 만든 추가 질문 답변. 서비스에서는 아래 추가 질문 API 응답과 같다 |

## 쪽 객체

`pages["2"]`처럼 쪽 번호로 찾는다. `GET /api/v1/documents/{document_id}/pages/{page_number}/learning`의 응답과 같다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `page_number` | 정수 | 원본 PDF 쪽 번호 |
| `analysis.summary` | 문자열 | 이 쪽의 요약 |
| `analysis.concepts[]` | 배열 | 핵심 개념. 개념마다 `name`과 근거 `evidence_block_ids`가 있다 |
| `analysis.coverage` | 문자열 | 원문이 어디까지 설명하는지 |
| `analysis.question_eligible` | 불리언 | `false`면 질문을 만들지 않은 쪽이다. 이때 `questions`는 빈 배열이다 |
| `analysis.exclusion_reason` | 문자열 또는 `null` | 제외 이유. `cover`(표지), `no_text`(읽을 본문 없음), `insufficient_text`(제목·그림뿐), 또는 모델이 쓴 짧은 이유 |
| `questions[]` | 배열 | 탐구 질문. 적격 쪽은 항상 2~3개다. 아래 질문 객체 참고 |
| `width_pt`, `height_pt` | 실수 | 추출 좌표의 기준이 된 페이지 크기 |
| `evidence_blocks[]` | 배열 | 이 쪽 모든 블록의 `block_id`와 `bbox`. 근거 위치를 그릴 때 쓴다 |
| `research_status` | 문자열 | `disabled`(과목의 연구 동향 꺼짐), `ready`(검색 완료, 질문에 맞는 논문이 없으면 비어 있을 수 있음), `unavailable`(검색·요약 실패) |

## 질문 객체

`pages["2"].questions[0]`처럼 쪽 안의 순서로 찾는다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `type` | 문자열 | 질문 관점. `connect_prior`(이전 내용과 연결하기), `understand_flow`(전체 흐름에서 이해하기), `challenge`(당연한 내용 의심하기), `apply`(실제 상황에 적용하기), `extend`(강의 밖으로 확장하기) |
| `question` | 문자열 | 학생이 스스로 던질 법한 의문문. 물음표로 끝난다 |
| `why_recommended` | 문자열 | 이 질문을 추천하는 이유 두 문장. 화면에 "추천 이유" 같은 머리말 없이 그대로 보여 준다 |
| `evidence_block_ids` | 문자열 배열 | **질문의 근거가 된 원문 블록 ID.** 1개 이상이고 항상 같은 쪽의 본문 블록이다 |
| `explanation.headline` | 문자열 | 더 알아보기 해설의 한 줄 핵심 |
| `explanation.body` | 문자열 | 강의 근거와 이유를 담은 세네 문장 |
| `explanation.flow` | 문자열 배열 | 개념이 이어지는 흐름 2~4단계. 화살표로 이어 보여 준다 |
| `related_courses[]` | 배열 | 더 알아보기의 이어서 볼 과목. 아래 참고. 후보가 없으면 빈 배열 |
| `trends[]` | 배열 | 더 알아보기의 연구 동향. 아래 참고. 질문에 맞는 논문이 없으면 빈 배열 |
| `prerequisites` | 문자열 배열 | 선행 개념. "개념 — 먼저 알아야 하는 이유" 형식 |
| `learning_steps` | 문자열 배열 | 학습 순서 1~3단계 |
| `first_activity` | 문자열 | 바로 해 볼 첫 활동 |

`prerequisites`, `learning_steps`, `first_activity`는 main `question` 테이블의 `prerequisite`, `learning_order`, `first_activity` 컬럼에 대응한다. 더 알아보기 화면에는 해설·이어서 볼 과목·연구 동향만 써도 된다.

### 실제 예시

[examples/learning.example.json](examples/learning.example.json)의 2쪽 첫 질문이다. 긴 문장은 `…`로 줄였고, 연구 동향은 두 편 중 한 편만 옮겼다.

```json
{
  "type": "understand_flow",
  "question": "테이블을 분해하면 왜 갱신 이상이 줄어들까요?",
  "why_recommended": "정규화의 핵심 목적인 데이터 무결성 유지 원리를 이해하는 데 중요합니다. …",
  "explanation": {
    "headline": "데이터 중복을 제거하여 한 곳만 수정해도 전체 데이터가 일관성을 유지하기 때문입니다.",
    "body": "원본 테이블에서는 과목 정보가 학생마다 반복되어, 과목의 강의실이 바뀔 때 모든 학생 행을 찾아 수정해야 하는 갱신 이상이 발 …",
    "flow": ["데이터 중복", "갱신 이상 발생", "테이블 분해", "데이터 일관성 확보"]
  },
  "evidence_block_ids": ["p2-b2", "p2-b3"],
  "related_courses": [
    {
      "course_id": "…",
      "name": "이산수학",
      "relation": "previous",
      "reason": "이산수학의 '관계' 단원에서 다루는 집합 간의 대응과 함수 개념은 데이터베이스의 함수 종속 …",
      "next_topic": "관계의 성질과 함수 종속성. 관계의 반사성, 대칭성, 추이성 개념을 통해 데이터베이스의 함 …",
      "source": "ai_recommendation"
    },
    {
      "course_id": "…",
      "name": "데이터베이스응용",
      "relation": "next",
      "reason": "데이터베이스응용의 '정규화' 단원에서 테이블 분해를 직접적으로 다룹니다. 갱신 이상을 방지 …",
      "next_topic": "정규화의 단계별 적용. 제1정규형부터 제3정규형까지 각 단계에서 중복이 어떻게 제거되는지 …",
      "source": "ai_recommendation"
    }
  ],
  "trends": [
    {
      "paper_id": "789b3d2f277639bfb8781b285e0ef410ea217f58",
      "title": "SocietySync ERP - A Normalized Relational Database Architecture for Residential Management",
      "year": 2026,
      "summary": "아파트 관리 업무의 수기 기록 방식에서 발생하는 비효율성과 부정확성 문제를 다룹니다. …",
      "url": "https://www.semanticscholar.org/paper/789b3d2f277639bfb8781b285e0ef410ea217f58",
      "searched_at": "2026-11-19T19:45:27.292329Z",
      "source": "semantic_scholar"
    }
  ],
  "prerequisites": ["…"],
  "learning_steps": ["…"],
  "first_activity": "…"
}
```

## 근거 블록 ID로 원문 위치 표시하기

질문마다 근거 블록 ID를 저장하므로 프런트는 PDF 위에 근거 위치를 그릴 수 있다.

1. 질문의 `evidence_block_ids`에 있는 ID를 같은 쪽 `evidence_blocks[]`의 `block_id`에서 찾는다.
2. `bbox`는 `[left, top, right, bottom]`이다. 원점은 페이지 좌상단이고 값은 0~1로 정규화돼 있다. 렌더링한 페이지의 너비와 높이를 곱하면 화면 좌표가 된다. 예를 들어 `bbox[0] × 화면 너비`가 왼쪽 위치다.
3. 질문 표시(`?`)는 첫 근거 블록 근처에 두고, 질문을 누르면 근거 블록 전부를 강조한다.

`block_id`는 입력 추출 JSON의 블록 ID와 같다. 근거 원문 텍스트가 필요하면 추출 JSON에서 같은 ID의 `text`나 `table`을 읽는다. 결과 JSON에는 원문 텍스트를 다시 넣지 않는다.

## 이어서 볼 과목

| 필드 | 설명 |
| --- | --- |
| `course_id` | DB `course.id`. 명령줄에서는 실행마다 새로 만든 임시 ID다 |
| `name` | 과목명 |
| `relation` | `previous`(이 과목보다 앞 학기에 듣는 관련 과목), `next`(뒤 학기에 들을 과목), `related`(이 과목의 편성 학기를 모를 때) |
| `reason` | 이 질문이 그 과목의 어떤 주차 주제와 어떻게 이어지는지 두세 문장 |
| `next_topic` | `previous`면 다시 볼 주제, `next`면 이어서 배울 주제와 확인할 점 |
| `source` | 항상 `ai_recommendation`. 공식 교육과정 관계가 아니라 AI 추천이라는 뜻이다 |

후보는 교육과정 ZIP의 과목별 계획서 주제 벡터를 pgvector로 조회해 찾는다. 이 과목보다 앞 학기 과목 3개와 뒤 학기 과목 3개를 고르고, 같은 학기 과목은 빼며, Gemini가 그중 질문에 맞는 과목을 고른다. 교육과정 ZIP의 공식 선수과목(`official_prerequisites`)은 현재 52과목 모두 비어 있어 선수과목으로 표시하는 항목은 없다. 화면에는 "AI 추천"임을 함께 보여 준다.

## 연구 동향

| 필드 | 설명 |
| --- | --- |
| `paper_id` | Semantic Scholar 논문 ID. Gemini 대체 항목은 `gemini-1`처럼 붙인다 |
| `title` | 논문 제목. Gemini 대체 항목은 연구 방향의 이름 |
| `year` | 출판 연도. Gemini 대체 항목은 `null` |
| `summary` | 초록에만 근거한 한국어 요약 세 문장 안팎 |
| `url` | 원문 링크. Gemini 대체 항목은 Google Scholar 검색 링크 |
| `searched_at` | 검색 시점 |
| `source` | `semantic_scholar` 또는 `gemini` |

연구 동향을 켠 과목만 검색한다. 과목명과 계획서 주제로 검색어를 2~3개 만들어 최근 5년 논문을 모으고, 질문마다 관련된 논문을 2편까지 고른다. Semantic Scholar 검색이 모두 실패하면 Gemini가 특정 논문을 지어내지 않고 연구 방향만 정리하며, 이때 `source`가 `gemini`다. 화면에는 "AI 정리 · 논문 검색 결과 아님"처럼 구분해 보여 준다.

## 추가 질문 응답

`POST /api/v1/documents/{document_id}/pages/{page_number}/ask`에 `{"question": "…"}`를 보내면 아래 형식으로 답한다. 명령줄의 `follow_up`도 같은 형식에 `page_number`와 `question`이 더 붙는다.

| 필드 | 설명 |
| --- | --- |
| `explanation` | 답변. 결론을 먼저 쓰고 "강의자료에서는:", "보충 설명:", "예시:", "더 공부하려면:" 머리말로 단락을 나눈다. 빈 줄 없이 머리말을 이어 쓰는 경우가 있어 화면에서는 머리말 앞에서 단락을 나누면 읽기 좋다 |
| `evidence_block_ids` | 답변의 근거 블록 ID. 같은 쪽 블록이며, 질문 근거와 같은 방법으로 강조할 수 있다 |

오류 코드는 다음과 같다. 404는 결과가 아직 없거나 다른 사용자의 문서, 409는 질문을 만들지 않은 쪽, 503은 서버에 Gemini 키가 없음, 502는 근거가 있는 답변을 만들지 못함을 뜻한다.

## 화면과 필드 대응

| 화면 | 쓰는 필드 |
| --- | --- |
| 쪽별 발견 질문 카드 | `questions[].type`, `question`, `why_recommended` |
| 슬라이드 위 `?` 표시 | `questions[].evidence_block_ids[0]`와 `evidence_blocks[].bbox` |
| 질문을 눌렀을 때 근거 강조 | `questions[].evidence_block_ids` 전체 |
| 더 알아보기: 해설 | `explanation.headline`, `explanation.body`, `explanation.flow` |
| 더 알아보기: 이어서 볼 과목 | `related_courses[]`. `relation`으로 이전에 들은 과목과 이후에 들을 과목을 나눈다 |
| 더 알아보기: 연구 동향 | `trends[]`와 쪽의 `research_status` |
| 질문을 만들지 않은 쪽 | `analysis.question_eligible`, `analysis.exclusion_reason` |
| 이어서 질문하기 | 추가 질문 API의 `explanation`, `evidence_block_ids` |

## 생성할 때 보장하는 것

결과를 저장하기 전에 아래를 검사한다. 어기면 그 3쪽 묶음만 최대 세 번 다시 요청하고, 그래도 맞지 않으면 작업 전체를 다시 시도한다.

- 적격 쪽의 질문은 2~3개, 제외 쪽은 0개이며 같은 쪽의 질문 문장은 서로 다르다.
- 질문과 개념의 근거 블록 ID는 같은 쪽의 본문 블록에만 있다. 머리말·꼬리말과 다른 쪽 블록은 거부한다.
- 이어서 볼 과목과 논문은 검색한 후보 안에서만 고른다. 모델이 지어낸 과목·논문은 거부한다.
- 해설의 `flow`는 2~4단계, 학습 순서는 1~3단계, 질문별 과목은 4개, 논문은 2편 이하다.

질문이 유용한지와 해설이 정확한지는 자동으로 검사하지 않는다. 생성물을 원문과 대조해 검토한다.

## main에 합칠 때 확인할 점

- main의 `question` 테이블에는 `explanation`, `evidence_block_ids`, `related_courses`, `trends` 컬럼이 없다. 질문 저장 API와 같은 질문으로 연결하려면 이 필드를 저장할 곳이 필요하다. 지금은 문서 단위 결과 전체를 `document_learning.result`(JSONB)에 저장한다.
- 이 브랜치의 Alembic 리비전(`c4ab0f5b3168` → `5d2e7a1c9b40`)과 main의 head를 하나의 경로로 잇는다.
- 편성 학기 컬럼을 추가하기 전에 과목을 인덱싱했다면 교육과정 ZIP을 한 번 더 인덱싱한다.
