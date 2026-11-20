# 탐구 질문 실행과 저장

## 코드 위치

| 위치 | 역할 |
| --- | --- |
| `backend/app/pipelines/learning.py` | 추출 JSON → 쪽별 질문·원문 근거·해설·학습 경로 |
| `backend/app/pipelines/learning_cli.py` | JSON 파일로 위 과정을 실행하는 명령줄 |
| `backend/app/services/curriculum_search.py`, `research.py` | 과목 후보 검색, 연구 동향 조회·캐시 |
| `backend/app/worker/run.py`, `backend/app/api/documents.py` | 추출·결과 JSON과 기존 질문 행을 저장하고 쪽별 조회·추가 질문에 사용 |

## 빠른 검증

백엔드 의존성을 설치한 뒤 `backend/`에서 실행한다. 실제 생성에는 `../.env`에 `GEMINI_API_KEY`와 사용 가능한 `GEMINI_TEXT_MODEL`이 필요하다.

```bash
python -m unittest discover -s tests -v
python -m app.pipelines.learning_cli extraction.json -o learning.json --env-file ../.env
```

추천 과목도 보려면 `--corpus ieobom-ssu-corpus.zip --course-code 21501666`, 연구 동향은 `--trends`, 추가 답변은 `--page 2 --ask "정규화하면 조회 비용도 항상 줄어드나요?"`를 추가한다. Semantic Scholar 키가 있으면 `SEMANTIC_SCHOLAR_API_KEY`에 설정한다. [출력 예시](examples/learning.example.json)

## 서비스 연결

`alembic upgrade head`는 main과 질문 생성 마이그레이션을 `a6c14e9b820f`로 연결한다.
워커는 공통 Docling 추출 JSON을 `generate_learning()`에 전달한다. 적격 페이지마다 질문 두 개를
만들고, 3쪽 묶음이 끝날 때마다 상태 API에 진행 페이지 수를 기록한다. [저장 구조](extraction/storage.md)

추천 과목을 사용하려면 대상 커리큘럼을 먼저 등록하고 아래 명령으로 주제·편성 학기를 인덱싱한다.
숭실대 데이터는 팀원이 정리한 자료를 받을 때 등록하며, 배포 과정에서 자동으로 넣지 않는다.

```bash
python -m app.services.curriculum_search ieobom-ssu-corpus.zip --curriculum-id <curriculum_uuid>
```

검색은 같은 커리큘럼 안에서 수행한다. `previous`·`next`는 편성 학기 기준이며 실제 수강 여부는
응답의 `enrollment_status`로 구분한다. 독립 CLI의 과목 UUID는 임시 값이므로 서비스 DB에 직접
적재하지 않는다. 서버 생성 경로는 DB의 과목 ID를 사용한다.
