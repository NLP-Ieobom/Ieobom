# 숭실대 AI소프트웨어학부 과목 연결 그래프

2026학년도 입학생 기준 교육과정의 52과목, 학년·학기 배치, 소프트웨어·정보보호·인공지능·AI시스템 세부전공을 정리했다. 2026년 개설 학수번호를 확인한 49과목은 학수번호와 연결했다. 서버프로그래밍·분산컴퓨팅·빅데이터컴퓨팅은 교육과정에 포함되며 별도 교육과정 ID를 사용한다. [학부 교육과정표](https://ai.ssu.ac.kr/api-server/resource/download/327) · [세부전공 소개](https://ai.ssu.ac.kr/department/concentration)

화살표는 먼저 익히면 다음 과목을 이해하거나 프로젝트에 적용하는 데 도움이 되는 방향이다. 각 연결에 시연용 추천 상태와 연결 이유, 참고한 교육과정·계획서 맥락을 기록했다. [그래프 JSON](../../backend/app/data/ssu_ai_software_2026.json)

## 그래프 미리보기

저장소 루트에서 HTML 파일을 생성해 브라우저에서 연다. HTML 파일은 인터넷 연결 없이 열 수 있다.

```sh
python docs/course-graph/build_preview.py --output tmp/course-graph.html
```

과목을 선택하면 해당 과목에 들어오고 나가는 추천 연결과 이유를 볼 수 있다. 세부전공 필터와 과목명 검색으로 목록을 좁힐 수 있다.

## 백엔드에 등록

DB 환경 변수를 준비한 뒤 `backend/`에서 실행한다.

```sh
alembic upgrade head
python -m app.scripts.seed_ssu_curriculum
```

로그인 후 `GET /api/v1/curricula`에서 숭실대 AI소프트웨어학부 2026학년도 항목을 찾고, `GET /api/v1/curricula/{curriculum_id}/map`에 그 UUID를 넣는다. 기존 API의 `courses`와 `relations`에 과목과 연결이 들어간다. 해당 그래프 연결은 `relation_type=recommended`, `source=ssu_2026_provisional`로 식별한다. 학기·세부전공·연결 이유는 그래프 JSON에서 확인할 수 있다. [지도 API 명세](../api.md#커리큘럼과-과목)

같은 DB에서 다시 실행하면 등록된 과목 UUID와 수강·문서 참조를 보존하며, 이 시드가 관리하는 추천 연결을 동기화한다. 질문별 관련 과목 추천에 쓰는 학습 프로필은 [기존 코퍼스 등록 명령](../architecture.md#데이터-준비와-남은-범위)으로 생성한다.
