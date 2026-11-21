# PDF 추출·질문 저장

워커는 공통 Docling 추출기로 v1 JSON을 만들고 `document_learning.extraction`에 저장한다.
원본 PDF는 S3에 있고, 페이지 이미지는 따로 만들거나 S3에 저장하지 않는다. 텍스트 없는 그림은
좌표만 남으며 현재 Gemini 입력에는 텍스트와 표 셀만 전달한다.

| 데이터 | 저장 위치 |
| --- | --- |
| 원본 파일과 전체 페이지 수 | `document.s3_key`, `original_filename`, `page_count` |
| 문서 메타데이터, 페이지별 블록·본문·표·좌표 | `document_learning.extraction` JSONB |
| 페이지 분석과 생성 결과 전체 | `document_learning.result` JSONB |
| 메모·질문이 참조하는 페이지 ID | `document_page.id` |
| 질문 본문·유형·학습 안내 | 기존 `question` 컬럼 |
| 짧은 해설·긴 해설·개념 흐름 | `question.explanation`의 `headline`, `body`, `flow` |
| 질문의 근거 ID와 해당 좌표 | `question.evidence_block_ids`, `evidence_blocks` |
| 질문별 추천 과목·연구 동향 | `question.related_courses`, `trends` |

추출 원문의 `pages[].blocks`는 순서와 ID를 유지한다. `source.filename`은 워커의 임시 파일명 대신
`document.original_filename`을 사용한다. 좌표 규칙은 [추출 형식](README.md#pdf)을 따른다.

추출을 저장할 때 `(document_id, page_number)`로 페이지 행을 만든다. 메모 API가 먼저 만든 행이
있으면 기존 ID를 유지한다. 질문 생성에 실패해 재시도할 때는 DB에 저장된 추출 원문을 재사용한다.

적격 페이지마다 질문은 정확히 두 개다. 질문별 `evidence_block_ids`가 같은 페이지에 존재하는지
검증하고 해당 좌표를 질문 행에 복사한다. `document_learning.result`의 각 질문에도 같은
`question.id`를 기록한다. 질문 행·결과 JSON·잡 성공 상태는 한 트랜잭션으로 저장한다.
재추출이나 이미 생성된 질문의 교체 기능은 제공하지 않는다.

기존 `prerequisite`·`learning_order` 문자열에는 배열 항목을 줄바꿈으로 연결해 저장한다.
`/learning` 응답의 `prerequisites`·`learning_steps`는 생성된 배열 그대로다. 기존 질문 데이터는
근거·과목·동향 배열이 비어 있고 해설이 NULL인 상태로 유지한다.

`/learning`과 기존 `/questions` 응답은 같은 질문 ID를 반환한다. 질문 저장 여부와 추천 과목의
수강 상태는 조회 시점에 붙인다. GET 요청은 열람 진도를 변경하지 않으며, 진도 기록은 기존
문서 `/progress` PUT을 사용한다. [API 명세](../api.md#페이지-분석과-질문)

Gemini 키가 없으면 추출과 페이지 수만 저장하고 `analysis_skipped`로 끝난다. 질문 생성까지
끝나면 `completed`가 된다. [폴링 상태](../api.md#분석-상태와-재시도)
