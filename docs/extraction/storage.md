# PDF 추출 결과 DB 저장 검토

현재 워커는 S3에서 PDF를 받은 뒤 공통 추출기를 실행하고, 결과 JSON을 로컬 출력 디렉터리에 남긴다. `analysis_job.status`는 변환 결과에 따라 바꾸지만 추출 내용을 DB에 저장하지는 않는다. 따라서 지금의 `succeeded`는 PDF 변환 성공만 뜻한다. 분석·질문 생성까지 완료했다는 의미로 쓰려면 단계 연결이 더 필요하다.

`document`에는 원본 파일명과 S3 키가 있고, `document_page`에는 문서 ID와 페이지 번호만 있다. 페이지·블록 JSON을 저장할 컬럼은 없다. 아래는 저장 제안이며 아직 모델이나 마이그레이션에 반영하지 않았다. JSON 필드의 의미와 좌표 규칙은 [추출 형식](README.md#pdf)을 따른다.

## 페이지 단위 저장

페이지 조회가 기본이므로 `document_page`에 크기와 `blocks`를 추가하는 방식이 단순하다. 블록과 표 셀은 페이지와 함께 읽으므로 우선 JSONB 배열로 보관한다. 배열 순서를 유지하면 읽기 순서도 보존된다.

| 추출 결과 | 저장 위치 제안 | 타입 |
| --- | --- | --- |
| `document_id` | 기존 `document.id`와 일치하는지 확인 | UUID |
| `schema_version`, `source`, `coordinate_system`, `warnings` | `document.extraction_metadata` | JSONB |
| `pages[].page_number` | 기존 `document_page.page_number` | integer |
| `pages[].width_pt`, `height_pt` | `document_page.width_pt`, `height_pt` | double precision |
| `pages[].blocks` | `document_page.blocks` | JSONB |

`extraction_metadata`와 페이지의 추가 컬럼은 처음에는 NULL을 허용한다. 추출 전에 메모 API가 페이지 행을 만들 수 있고, 기존 시연 데이터에도 추출 결과가 없기 때문이다. `blocks = NULL`은 미추출, `blocks = []`는 추출은 됐지만 블록이 없는 페이지로 구분한다. 완료된 추출에는 크기와 블록 배열이 모두 있어야 한다.

`source.sha256`은 추출기가 실제 파일에서 계산한 값을 저장한다. 워커의 임시 입력 파일명은 `{document_id}.pdf`이므로, 저장할 `source.filename`은 `document.original_filename`으로 채운다. 추출 JSON을 다시 조립할 때 문서 ID와 원본 파일명을 이 문서 레코드에서 가져오면 된다. 원본 PDF는 기존 S3 키로 조회한다.

블록의 `block_id`, `kind`, `docling_label`, `text`, `bbox`, `table`은 변형 없이 저장한다. 표 셀이나 좌표를 따로 평탄화하지 않는다. 블록을 SQL로 직접 검색하거나 외래키로 참조할 필요가 생기면 그때 별도 테이블을 검토한다.

## 저장 시점과 재실행

PDF 변환 중에는 DB 쓰기 트랜잭션을 열어 두지 않는다. 결과를 받은 뒤 스키마, 문서 ID, 전체 페이지 수와 번호, 블록 ID의 고유성을 확인하고 한 트랜잭션에서 문서 메타데이터와 모든 페이지를 저장한다. 부분 변환·페이지 누락은 완료된 추출로 저장하지 않는다. `no_text` 경고는 그대로 남기고, 빈 페이지도 원래 페이지 번호로 저장한다.

페이지는 기존 `(document_id, page_number)` 유니크 제약을 기준으로 upsert한다. 메모와 질문이 페이지 ID를 참조하므로 기존 페이지 행을 삭제하고 새 UUID로 다시 만들면 안 된다. 추출 데이터만 갱신하고 `id`는 유지한다.

페이지 저장과 `analysis_job.completed_step = 'parse'` 기록을 같은 트랜잭션에서 커밋하는 것을 제안한다. `completed_step`은 현재 없는 컬럼이다. 다음 분석 단계에서 실패해도 이 값을 보고 저장된 페이지부터 이어 갈 수 있다. DB 오류가 나면 전체를 롤백하고 parse 완료로 기록하지 않는다. 전체 잡의 `succeeded`는 마지막 검증 단계까지 끝난 뒤에 기록한다.

재추출하면 `block_id`가 달라질 수 있다. 우선 생성 결과가 없는 문서에만 재추출을 허용하는 방식이 단순하다. 생성 결과가 있는 문서를 다시 추출하려면 이전 분석·질문을 함께 무효화할지, 추출 버전을 따로 보관할지 정해야 한다. 이 처리 없이 `blocks`만 덮어쓰면 기존 질문이 다른 원문을 가리킬 수 있다.

## 분석과 질문 연결

추출 단계에서는 `analysis`를 만들지 않는다. 이후 분석 결과는 아키텍처에 있는 `page_analysis`, `page_concept`에 저장하고, JSON을 반환할 때 페이지의 `analysis`로 조립하면 된다. 두 모델은 아직 없다. 제외 페이지도 유지하고 `question_eligible`, `exclusion_reason`을 분석 결과에 기록한다.

현재 `question`은 `document_page_id`만 참조한다. 블록 강조 표시를 연결하려면 질문에 `evidence_block_ids` 같은 JSONB 배열을 추가해야 한다. 질문 저장 시 모든 ID가 해당 페이지의 `blocks`에 있는지 확인한다. JSONB 내부 ID에는 일반 외래키를 걸 수 없으므로 이 검증은 저장 코드가 맡는다. 기존 질문에는 블록 근거가 없다는 점도 조회 시 구분해야 한다.

이번에 필요한 저장 구현은 문서·페이지 컬럼 추가와 워커의 parse 저장까지다. 분석·질문 모델 변경은 해당 생성 단계에서 적용하면 된다. 지금은 추출 설정과 JSON 출력 연결까지만 반영했다.
