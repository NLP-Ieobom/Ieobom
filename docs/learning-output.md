# 프런트에서 읽는 JSON

[실제 생성 예시](examples/learning.example.json)에서 `pages["2"]`는 GET `/learning`의 응답이다. 팀의 [PDF 추출 v1 JSON](https://github.com/NLP-Ieobom/Ieobom/blob/pdf_extraction/docs/extraction/README.md)이 입력이다.

| 화면 | 필드 |
| --- | --- |
| 발견 질문 카드 | `questions[]`의 `question`, `type`, `why_recommended` |
| PDF 위 물음표와 원문 강조 | `questions[].evidence_block_ids` → `evidence_blocks[].block_id` → `bbox` |
| 더 깊이 알아보기 | 질문의 `explanation.headline`·`body`·`flow`, `prerequisites`, `learning_steps`, `first_activity` |
| 이어서 볼 과목 | 질문의 `related_courses[]`. `name`, `reason`, `next_topic`을 쓰고 `relation`으로 앞 학기(`previous`)·뒤 학기(`next`)·학기 미확인(`related`)을 구분한다. |
| 연구 동향 | 질문의 `trends[]`. 제목·요약·연도·링크를 보여주고 `source`로 Semantic Scholar 논문(`semantic_scholar`)과 Gemini가 정리한 연구 방향(`gemini`)을 구분한다. |

`bbox = [left, top, right, bottom]`은 좌상단 기준 0~1 좌표다. 페이지 렌더링 크기를 곱해 첫 근거 옆에 물음표를 놓고, 질문을 선택하면 같은 쪽의 근거 전체를 강조한다.

표지 등은 `analysis.question_eligible: false`와 `questions: []`로 온다. 과목·동향 배열도 해당 결과가 없으면 비어 있다. 쪽의 `research_status`는 `disabled`, `ready`, `unavailable` 중 하나다.

## 추가 질문

POST `/ask` 본문으로 `{"question":"정규화하면 조회 비용도 항상 줄어드나요?"}`를 보내면 다음 구조를 받는다.

```json
{
  "explanation": "정규화로 분해한 테이블을 조회할 때 조인이 더 필요할 수 있습니다.",
  "evidence_block_ids": ["p2-b2"]
}
```

예시 파일의 `follow_up`에는 응답 필드에 더해 테스트에 사용한 `page_number`와 `question`이 있다. 결과가 준비되기 전에는 문서 상태를 확인한다. 질문이 제외된 쪽에 추가 질문을 보내면 409가 온다.
