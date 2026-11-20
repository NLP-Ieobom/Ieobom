# 이어봄 · 탐구 질문

`making_question` 브랜치는 PDF 추출 v1 JSON에서 **발견 질문, 원문 근거, 해설, 관련 과목, 연구 동향**을 만든다.

## 프런트에서 호출할 API 2개

두 API에는 로그인 토큰과 문서 ID, 원본 PDF 쪽 번호(1부터 시작)를 사용한다.

| 호출 | 쓰는 곳 |
| --- | --- |
| `GET /api/v1/documents/{document_id}/pages/{page_number}/learning` | 쪽을 열 때 저장된 발견 질문, 물음표 좌표, **더 깊이 알아보기** 데이터를 받는다. |
| `POST /api/v1/documents/{document_id}/pages/{page_number}/ask` | 학생의 입력을 `{"question":"…"}`로 보내면 답변과 근거 블록 ID를 받는다. |

## 예시 JSON

[실제 생성 결과](docs/examples/learning.example.json)의 `pages["2"]`가 GET 응답과 같은 구조다. `follow_up`에서 POST 답변의 `explanation`과 `evidence_block_ids`를 볼 수 있다.

- **발견 질문**은 `questions[]`를 읽고, 물음표는 `evidence_block_ids`를 `evidence_blocks[]`의 좌표에 연결한다.
- **더 깊이 알아보기**는 선택한 질문의 `explanation`, `related_courses[]`, `trends[]`를 읽는다.

[화면별 JSON 필드](docs/learning-output.md) · [코드 위치, 실행 방법, main 통합](docs/learning.md)
