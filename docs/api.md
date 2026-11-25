# 프론트 연동 API 명세

현재 라우터 31개 기준. 구조는 [architecture.md](architecture.md), 실행 가능한 요청은
[Swagger](https://13-209-160-89.sslip.io/docs), 기계용 스키마는
[OpenAPI](https://13-209-160-89.sslip.io/openapi.json)에서 확인한다.

[공통 규칙](#공통-규칙) · [인증](#인증) · [커리큘럼·과목](#커리큘럼과-과목) ·
[PDF](#pdf-등록과-조회) · [분석 상태](#분석-상태와-재시도) · [질문](#페이지-분석과-질문) ·
[메모·진도](#메모와-열람-진도) · [채팅](#추가-질문과-상태-확인) · [화면 연결](#화면-연결-순서)

## 공통 규칙

Base URL은 `https://13-209-160-89.sslip.io/api/v1`이다. 아래 경로는 이 주소 뒤에 붙인다.
로컬은 `http://localhost:8000/api/v1`을 사용한다. `/health`만 접두사 밖에 있다.

- 인증 예외로 표시한 API 외에는 `Authorization: Bearer <access_token>`이 필요하다.
  Swagger Authorize에는 토큰 값만 넣는다.
- 본문은 JSON이며 `Content-Type: application/json`을 사용한다. S3 PUT만 PDF 원본 바이트다.
  본문 필드는 선택으로 표시하지 않았으면 모두 필수다.
- `{..._id}`는 UUID 문자열인 필수 경로 변수다. `{page_number}`는 1부터 시작하는 원본 PDF 페이지 번호다.
  페이지에 인쇄된 쪽번호나 배열 인덱스가 아니다. 선택 쿼리는 쓰지 않을 때 아예 생략한다.
- 표에서 `없음`은 쿼리·본문이 없다는 뜻이다. `204`에는 응답 본문이 없으므로 `response.json()`을 호출하지 않는다.
- 목록은 페이지네이션 없이 반환한다. 항목이 없으면 `[]`, 아직 모르는 값은 `null`이다.
  날짜는 시간대가 포함된 ISO 8601 문자열이다. 아래 TypeScript 타입은 JSON 응답의 필드 설명이다.

| 공통 오류 | 의미 |
| --- | --- |
| `401` | 만료·잘못된 토큰 또는 로그인 실패 |
| `403` | Bearer 헤더 누락·인증 형식 오류 |
| `404` | 자원이 없거나 본인의 문서·질문이 아님 |
| `422` | UUID, 페이지 번호, 필수 필드, enum 등 입력 오류 |

업무 오류는 `{"detail":"document not found"}`처럼 문자열로 온다. 입력 검증 오류는
`{"detail":[{"loc":["body","page_number"],"msg":"...","type":"..."}]}` 형태다.
HTTP 상태로 분기하고 `detail`이 문자열인지 배열인지 구분한다. 개별 오류는 아래 표에 추가로 적었다.
브라우저의 프론트 Origin은 API와 S3 버킷의 CORS 설정에 각각 허용되어 있어야 한다.

## 인증

| API | 입력 | 성공 | 추가 오류 |
| --- | --- | --- | --- |
| `POST /auth/signup` | 본문 `{email: string, password: string}`. 이메일 형식, 비밀번호 8자 이상. 인증 불필요 | `200 TokenResponse` | `409` 이미 등록된 이메일 |
| `POST /auth/login` | 본문 `{email: string, password: string}`. 인증 불필요 | `200 TokenResponse` | `401` 이메일·비밀번호 불일치 |
| `POST /auth/refresh` | 본문 `{refresh_token: string}`. access token 불필요 | `200 TokenResponse` | `401` 만료·폐기된 refresh token |
| `POST /auth/logout` | 본문 `{refresh_token: string}`. access token 불필요 | `204` | 무효·이미 폐기된 토큰도 `204` |
| `GET /auth/me` | 없음 | `200 UserResponse` | 공통 오류 |

```ts
type UUID = string;
type DateTime = string;
type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
};
type UserResponse = {
  id: UUID;
  email: string;
  role: string; // 가입 시 student
  created_at: DateTime;
};
```

현재 기본 설정은 access token 30분, refresh token 14일이다. 갱신 성공 시 토큰 두 개를 모두 교체한다.
이전 refresh token은 즉시 폐기되므로 여러 401에 대한 갱신 요청을 동시에 보내지 않는다.
갱신 실패 시 로그인 화면으로 돌아간다. 로그아웃은 전달한 refresh token을 폐기하며,
프론트에서도 두 토큰을 지운다. 이미 발급된 access token은 만료 전까지 유효하다.

## 커리큘럼과 과목

| API | 입력 | 성공 | 추가 오류 |
| --- | --- | --- | --- |
| `GET /curricula` | 없음 | `200 {curricula: CurriculumSummary[]}` | 공통 오류 |
| `GET /curricula/{curriculum_id}/map` | 없음 | `200 CurriculumMapResponse` | `404` 커리큘럼 없음 |
| `GET /courses` | 선택 쿼리 `curriculum_id: UUID` | `200 {courses: CourseSummary[]}` | `404` 지정한 커리큘럼 없음 |
| `GET /courses/me` | 선택 쿼리 `curriculum_id: UUID` | `200 {courses: CourseWithEnrollment[]}` | `404` 지정한 커리큘럼 없음 |
| `PUT /courses/{course_id}/enrollment` | 본문 `{status: "in_progress" 또는 "completed"}` | `200 {course_id: UUID, status: "in_progress" 또는 "completed"}` | `404` 과목 없음 |
| `DELETE /courses/{course_id}/enrollment` | 없음 | `204` | `404` 과목 없음 |

```ts
type EnrollmentStatus = "not_enrolled" | "in_progress" | "completed";
type ReadingProgress = {
  viewed_pages: number;
  total_pages: number | null;
  progress_percent: number | null;
};
type CurriculumSummary = {
  id: UUID;
  institution: string;
  department: string;
  entry_year: number;
  is_demo: boolean;
};
type CourseSummary = {
  id: UUID;
  curriculum_id: UUID | null;
  name: string;
  course_code: string | null;
  curriculum_year: number | null;
  year_level: number | null;
  semesters: number[];
  areas: string[];
};
type CourseWithEnrollment = CourseSummary & {
  enrollment_status: EnrollmentStatus;
  reading_progress: ReadingProgress;
};
type CurriculumMapResponse = {
  curriculum: CurriculumSummary;
  courses: CourseWithEnrollment[];
  relations: {
    id: UUID;
    source_course_id: UUID;
    target_course_id: UUID;
    relation_type: string;
    source: string;
    reason: string | null;
    confidence: string | null;
  }[];
};
```

`/courses`는 전체 과목, `/courses/me`는 내가 등록한 수강 중·완료 과목이다.
둘 다 `?curriculum_id=<UUID>`로 한 커리큘럼에 한정한다. 필터 없는 전체 목록에는 소속 미정 과목도 나온다.
과목은 이름순이며 커리큘럼 목록은 실제 자료가 데모보다 먼저 나온다.
`entry_year`는 입학 기준 교육과정 연도이고, `is_demo=true`는 임시 시연용 커리큘럼이다.
`year_level`은 교육과정표에 배치된 학년, `semesters`는 그 학년에서 개설되는 학기, `areas`는 영역 구분이다.
같은 학년의 1·2학기 양쪽에 열리는 과목과 두 영역에 걸친 과목이 있어서 둘 다 목록이다. `areas`는 어느
영역에도 속하지 않는 과목이 있어서 비어 있을 수 있다. 배치 자료가 없는 커리큘럼은 `year_level=null`,
`semesters=[]`, `areas=[]`로 내려간다.

하나의 커리큘럼 상세와 지도는 `/map`으로 받는다. 별도 `GET /curricula/{id}`는 없다.
지도에는 미수강 과목도 포함하므로 `enrollment_status`로 흑백·수강 중·완료 표시를 나눈다.
관계는 `source_course_id`에서 `target_course_id`로 연결한다. 화면 배치 좌표는 응답에 없다.
`reason`은 왜 그 순서로 이어지는지 적은 한두 문장이고 `confidence`는 `high`·`medium`·`low`다.
숭실대 2026 교육과정 연결은 전부 잠정 추천이라 공식 선수과목이 아니며, 근거가 없는 연결은 둘 다 `null`이다.
학년·학기·영역으로 거르는 쿼리는 두지 않는다. 연결의 절반 이상이 서로 다른 영역을 이어서 서버에서 거르면
관계가 잘린다. 과목과 관계를 모두 받아 화면에서 거른다.
관계가 없으면 `relations=[]`다. `source=ssu_2026_provisional`은 숭실대 AI소프트웨어학부 2026학년도
시연용 학습 순서를 뜻한다. 두 시연 데이터 출처(`ssu_2026_provisional`, `demo`)의
`relation_type=recommended`는 화면에 학습 추천으로 표시한다.

수강 상태는 사용자가 직접 바꾸며 완료에서 수강 중으로 되돌릴 수 있다. 등록 취소는 PDF·메모·진도를
지우지 않고 지도에서 `not_enrolled`로 바뀐다. 수강 등록 없이도 등록된 과목에 PDF를 올릴 수 있다.

## PDF 등록과 조회

| API | 입력 | 성공 | 추가 오류 |
| --- | --- | --- | --- |
| `GET /documents` | 필수 쿼리 `course_id: UUID` | `200 {documents: DocumentSummary[]}` | 항목이 없으면 빈 배열 |
| `POST /documents/upload-url` | 아래 `UploadUrlRequest` 본문 | `200 UploadUrlResponse` | `400` PDF 외 MIME·용량 초과, `404` 과목 없음 |
| `POST /documents/{document_id}/complete` | 없음 | `200 {document_id: UUID, status: "uploaded", job_id: UUID}` | `409` 이미 완료·S3 파일 없음·크기 불일치 |
| `GET /documents/{document_id}/file-url` | 없음 | `200 {file_url: string, expires_in: number}` | `409` 업로드 미완료 |
| `DELETE /documents/{document_id}` | 없음 | `204` | `409` 분석 대기·실행 중, `503` 저장소·DB 삭제 실패 |

```ts
type DocumentReadingProgress = ReadingProgress & {
  last_page_number: number | null;
  last_viewed_at: DateTime | null;
};
type DocumentSummary = {
  document_id: UUID;
  filename: string;
  status: "pending_upload" | "uploaded";
  created_at: DateTime;
  reading_progress: DocumentReadingProgress;
};
type UploadUrlRequest = {
  course_id: UUID;
  filename: string;
  content_type: "application/pdf";
  size_bytes: number;
};
type UploadUrlResponse = {
  document_id: UUID;
  upload_url: string;
  s3_key: string;
  expires_in: number;
};
```

문서 목록은 해당 과목에 본인이 올린 PDF만 최신 등록순으로 반환한다. 아직 업로드를 완료하지 않은
문서도 포함한다. `status=uploaded`는 파일 등록 상태이며 질문 생성 완료를 뜻하지 않는다.

업로드 URL 요청 예시다. 실제 요청에서는 파일의 `name`, `size`를 사용한다. 현재 용량 상한은
50 MiB(52,428,800바이트)이며 URL 기본 유효기간은 업로드 900초, 열람 3,600초다. 만료 계산에는 응답의 `expires_in`을 쓴다.

```json
{
  "course_id": "11111111-1111-4111-8111-111111111111",
  "filename": "lecture.pdf",
  "content_type": "application/pdf",
  "size_bytes": 1048576
}
```

발급만으로 파일이 전송되지는 않는다. 받은 `upload_url`에 아래처럼 PUT한 뒤, 성공하면 `/complete`를
호출한다. S3 요청에는 서비스 Bearer 토큰을 붙이지 않으며 FormData로 감싸지 않는다.

```js
const response = await fetch(uploadUrl, {
  method: "PUT",
  headers: { "Content-Type": "application/pdf" },
  body: file,
});
if (!response.ok) throw new Error("PDF 업로드 실패");
// 이 다음 서비스 API의 /documents/{document_id}/complete 호출
```

`/file-url`은 원본 PDF 전체를 여는 URL이다. 질문 생성 중에도 사용할 수 있다. URL이 만료되면
다시 발급받는다. PDF를 페이지별 이미지 URL로 조회하는 API는 없다.

삭제는 PDF와 문서에 딸린 질문·저장 표시·메모·채팅·열람 기록·분석 결과를 제거한다. 수강 등록은 남는다.
`503`이면 같은 DELETE로 재시도하고, 이미 삭제된 문서의 재삭제는 `404`다. 업로드 중인 파일을 지울 때는
먼저 브라우저의 S3 전송을 중단한다. 분석 취소나 발급한 업로드 URL의 취소 기능은 없다.

## 분석 상태와 재시도

| API | 입력 | 성공 | 추가 오류 |
| --- | --- | --- | --- |
| `GET /documents/{document_id}/status` | 없음 | `200 StatusResponse` | 공통 오류 |
| `POST /documents/{document_id}/retry` | 없음 | `202 {document_id: UUID, job_id: UUID, job_status: "pending"}` | `409` 재시도 대상 아님, `503` 질문 생성 설정 없음 |

```ts
type StatusResponse = {
  document_id: UUID;
  status: "pending_upload" | "uploaded";
  job_status: "pending" | "running" | "succeeded" | "failed" | null;
  stage: "uploading" | "queued" | "downloading" | "extracting"
    | "analyzing" | "completed" | "analysis_skipped" | null;
  completed_pages: number | null;
  total_pages: number | null;
  stage_progress_percent: number | null;
  attempt: number;
  error_code: string | null;
  error_message: string | null;
  can_retry: boolean;
  next_retry_at: DateTime | null;
};
```

| 상태 | 프론트 표시·처리 |
| --- | --- |
| `stage=uploading` | S3 업로드·완료 요청 전. 전송률은 프론트에서 계산 |
| `pending / queued` | 분석 대기. `next_retry_at`이 있으면 자동 재시도 대기 |
| `running / downloading` | PDF 준비 중 |
| `running / extracting` | PDF 내용 추출 중. 퍼센트가 `null`이면 불확정 로딩 |
| `running / analyzing` | 질문 생성 중. 완료 페이지 / 전체 페이지와 단계 진행률 표시 |
| `succeeded / completed` | 폴링 중단, 현재 페이지 `/learning`과 필요한 질문 목록 새로 조회 |
| `succeeded / analysis_skipped` | 폴링 중단, 설정 미준비 안내. `can_retry=true`면 재시도 가능 |
| `failed` | 폴링 중단, `error_message` 표시. `can_retry=true`일 때 재시도 버튼 |

`/complete` 성공 이후 2~3초마다 조회한다. 실패 상태는 이전 `stage`를 유지하므로 `job_status=failed`
판정을 먼저 한다. 기존 데이터의 `stage=null`은 단계 미상으로 처리한다. 페이지를 바꿀 때마다 새 폴링을
만들지 않고 문서 단위로 유지하며, 뷰어를 떠나면 중단한다. 서버의 분석 작업은 계속된다.

`attempt`는 작업 실행 횟수이며 아직 실행 전이면 0이다. `completed_pages`, `total_pages`는 분석 진행용이고
사용자의 열람 진도와 다르다. 생성 제외 페이지도 처리 페이지 수에 포함된다.
진행률은 소요 시간 추정이 아닌 현재 분석 단계의 처리 페이지 비율이다. 추출 중에는 페이지 수·진행률이
`null`일 수 있고, 분석 중에는 3페이지 묶음마다 갱신한다. `100%`만 보고 완료로 판단하지 않는다.
질문은 마지막에 함께 저장하므로 12/27페이지를 처리했어도 앞 12페이지 질문이 먼저 나오지는 않는다.

오류 코드는 `AI_NOT_CONFIGURED`, `PDF_DOWNLOAD_FAILED`, `EXTRACTION_FAILED`, `EXTRACTION_TIMEOUT`,
`AI_TEMPORARY_ERROR`, `AI_REQUEST_FAILED`, `ANALYSIS_FAILED`, `WORKER_INTERRUPTED`를 사용한다.
자동 재시도 대기에서는 오류 정보가 남아 있어도 계속 폴링한다. 재시도 가능 여부는 코드명이 아닌 `can_retry`를 따른다.

수동 재시도는 실패 또는 분석 생략 상태에서 가능하다. `202`를 받으면 폴링을 다시 시작한다.
같은 잡의 `attempt`가 0으로 초기화되고, 저장된 추출·메모·진도는 유지한다. 완료된 질문을 다시 만드는 API는 아니다.

## 페이지 분석과 질문

PDF 우측 학습 패널은 `/learning` 하나로 구성할 수 있다. `/questions` 계열은 질문 목록 화면용이며
동일한 질문 UUID를 쓴다. 관련 과목·연구 동향을 별도로 호출하는 API는 없다.

| API | 입력 | 성공 | 용도 |
| --- | --- | --- | --- |
| `GET /documents/{document_id}/pages/{page_number}/learning` | 없음 | `200 StoredPageLearning` | 한 페이지의 요약·질문·해설·좌표 |
| `GET /documents/{document_id}/pages/{page_number}/questions` | 없음 | `200 {questions: QuestionResponse[]}` | 한 페이지의 질문만 |
| `GET /documents/{document_id}/questions` | 없음 | `200 {questions: QuestionResponse[]}` | PDF 전체 질문, 페이지 번호·생성 시각·ID 순 |
| `GET /questions` | 없음 | `200 {questions: QuestionResponse[]}` | 모든 PDF에서 내가 저장한 질문, 최근 저장순 |
| `PUT /questions/{question_id}/save` | 없음 | `204` | 저장 표시 추가. 이미 저장한 질문도 `204` |
| `DELETE /questions/{question_id}/save` | 없음 | `204` | 저장 표시 해제. 이미 해제한 질문도 `204` |

페이지 `/learning`·`/questions`는 업로드 미완료 또는 페이지 수 미확정이면 `409`, 범위 밖 페이지면 `422`다.
페이지 수가 확인된 유효 페이지라도 생성 결과가 아직 없으면 `/learning`은 `404`, `/questions`는 빈 배열이다.
PDF 전체 `/questions`는 페이지 수가 미확정이어도 조회 가능하며 질문이 없으면 빈 배열이다.
따라서 빈 질문 목록만으로 분석 완료 여부를 판단하지 않는다. 질문 저장 API도 타인·없는 질문은 `404`다.

```ts
type QuestionType = "connect_prior" | "understand_flow" | "challenge" | "apply" | "extend";
type EvidenceBlock = {
  block_id: string;
  bbox: [number, number, number, number];
};
type Explanation = {
  headline: string;
  body: string;
  flow: string[];
};
type CourseLink = {
  course_id: UUID;
  name: string;
  reason: string;
  next_topic: string;
  relation: "previous" | "next" | "related";
  source: "ai_recommendation";
  enrollment_status: EnrollmentStatus | null;
};
type ResearchTrend = {
  paper_id: string;
  title: string;
  summary: string;
  year: number | null;
  url: string;
  searched_at: DateTime;
  source: "semantic_scholar" | "gemini";
};
type StoredQuestionLearning = {
  id: UUID;
  type: QuestionType;
  question: string;
  why_recommended: string;
  explanation: Explanation;
  evidence_block_ids: string[];
  prerequisites: string[];
  learning_steps: string[];
  first_activity: string;
  related_courses: CourseLink[];
  trends: ResearchTrend[];
  is_saved: boolean;
};
type StoredPageLearning = {
  page_number: number;
  analysis: {
    summary: string;
    concepts: { name: string; evidence_block_ids: string[] }[];
    coverage: string;
    question_eligible: boolean;
    exclusion_reason: string | null;
  };
  questions: StoredQuestionLearning[];
  width_pt: number;
  height_pt: number;
  evidence_blocks: EvidenceBlock[];
  research_status: "disabled" | "ready" | "unavailable";
};
type QuestionResponse = {
  id: UUID;
  document_id: UUID;
  page_number: number;
  question_type: string;
  content: string;
  recommended_reason: string;
  prerequisite: string;
  learning_order: string;
  first_activity: string;
  created_at: DateTime;
  is_saved: boolean;
  evidence_block_ids: string[];
  evidence_blocks: EvidenceBlock[];
  explanation: Explanation | null;
  related_courses: CourseLink[];
  trends: ResearchTrend[];
};
```

응답 JSON은 [PDF 전체 질문 예시](examples/document-questions.example.json)를 참고한다.
UUID와 저장 표시는 예시 값이다. 실제 화면은 각 요청에서 받은 ID를 사용한다.

| `/learning` 질문 필드 | `/questions` 질문 필드 | 표시 |
| --- | --- | --- |
| `type` | `question_type` | 질문 유형 |
| `question` | `content` | 질문 문장 |
| `why_recommended` | `recommended_reason` | 추천 이유 |
| `prerequisites` 배열 | `prerequisite` 줄바꿈 문자열 | 먼저 알면 좋은 개념 |
| `learning_steps` 배열 | `learning_order` 줄바꿈 문자열 | 학습 순서 |
| 페이지의 `evidence_blocks`에서 ID 매칭 | 질문의 `evidence_blocks`에 직접 포함 | 원문 위치 |

`headline`은 짧은 답변, `body`와 `flow`는 더 알아보기의 자세한 해설이다.
새 적격 페이지는 질문 2개, 제외 페이지는 `question_eligible=false`, `questions=[]`다.
제외 사유는 고정 enum이 아니므로 알려지지 않은 값도 처리한다. 과거 질문은 한글 유형이나 빈 근거,
`explanation=null`이 있을 수 있다. 질문은 배열 순서 대신 UUID로 연결하고 좌표 없는 질문은 목록에서 보여 준다.

유형 표시는 `connect_prior=이전 내용과 연결하기`, `understand_flow=전체 흐름에서 이해하기`,
`challenge=당연한 내용 의심하기`, `apply=실제 상황에 적용하기`, `extend=강의 밖으로 확장하기`다.

추천 과목의 `previous`·`next`는 교육과정의 편성 학기 기준이다. 실제 수강 여부는 `enrollment_status`를 쓴다.
후보 데이터나 관련 결과가 없으면 `related_courses=[]`가 정상이며 공식 선수 관계로 표시하지 않는다.
`research_status=disabled`는 과목 설정 꺼짐, `unavailable`은 동향 생성 실패다.
`ready`여도 질문에 맞는 결과가 없으면 `trends=[]`일 수 있다. `source=gemini`는 논문 자체가 아닌
연구 방향 안내와 검색 링크이며 연도는 `null`이다.

### 원문 물음표 위치

`bbox=[left, top, right, bottom]`은 좌상단 기준 0~1 좌표다. `/learning`에서는 질문의
`evidence_block_ids`를 페이지 `evidence_blocks.block_id`와 연결한다. 페이지의 모든 블록을 질문 근거로
칠하지 않는다. PDF가 표시되는 실제 영역에 맞춰 아래 값을 계산한다.

```js
const [left, top, right, bottom] = block.bbox;
const rect = {
  left: left * pageWidth,
  top: top * pageHeight,
  width: (right - left) * pageWidth,
  height: (bottom - top) * pageHeight,
};
```

`pageWidth`, `pageHeight`는 여백·툴바를 제외한 PDF 페이지의 CSS 표시 크기다. 확대 시 재계산하고,
뷰어에서 추가 회전하면 좌표에도 같은 회전을 적용한다. `width_pt`, `height_pt`는 추출 기준 크기이지 CSS 픽셀이 아니다.
같은 블록에 질문이 여러 개 연결될 수 있으므로 하나의 물음표에 개수를 붙여 선택하게 하거나 겹치지 않게 배치한다.
블록 ID는 문서별로 반복될 수 있어 화면 식별 키에 문서 ID도 포함한다.

## 메모와 열람 진도

| API | 입력 | 성공 |
| --- | --- | --- |
| `GET /documents/{document_id}/pages/{page_number}/note` | 없음 | `200 NoteResponse` |
| `PUT /documents/{document_id}/pages/{page_number}/note` | 본문 `{content: string}` | `200 NoteResponse` |
| `GET /documents/{document_id}/progress` | 없음 | `200 DocumentProgressResponse` |
| `PUT /documents/{document_id}/progress` | 본문 `{page_number: number}`. 정수, 1 이상 | `200 DocumentProgressResponse` |

```ts
type NoteResponse = {
  document_id: UUID;
  page_number: number;
  content: string | null;
};
type DocumentProgressResponse = DocumentReadingProgress & {
  document_id: UUID;
};
```

메모 GET·PUT과 진도 PUT은 업로드 미완료 또는 페이지 수 미확정이면 `409`, 범위 밖 페이지면 `422`다.
진도 GET은 추출 전에도 가능하다. 이때 전체 페이지 수와 비율은 `null`일 수 있다.
메모가 없으면 `content=null`이고 지울 때는 `{"content":""}`를 PUT한다. 별도 메모 DELETE는 없다.

진도는 페이지가 실제 표시될 때 `{"page_number":5}`처럼 기록한다. 미리 불러오기·질문·메모 GET은 열람으로 세지 않는다.
같은 페이지를 여러 번 기록해도 `viewed_pages`는 한 번만 증가하고 마지막 위치는 매번 갱신된다.
빠르게 페이지를 이동할 때 오래된 PUT이 나중에 전송되지 않도록 요청 순서를 관리한다.

다음은 27페이지 중 서로 다른 3페이지를 보고 마지막으로 5페이지를 연 응답 예시다.

```json
{
  "document_id": "22222222-2222-4222-8222-222222222222",
  "viewed_pages": 3,
  "total_pages": 27,
  "progress_percent": 11.11,
  "last_page_number": 5,
  "last_viewed_at": "2026-11-21T07:00:00Z"
}
```

재진입 시 `last_page_number`로 이동하고 `null`이면 1페이지에서 시작한다. 마지막 위치는 서버에 마지막으로
기록된 페이지이며 종료 이벤트나 페이지 안의 스크롤 위치는 저장하지 않는다.
과목 진도는 본인의 업로드 완료 PDF를 합산하므로 새 PDF 추가·삭제로 비율이 달라질 수 있다.
일부 PDF의 페이지 수를 모르면 과목 전체 페이지 수와 비율도 `null`이다.
업로드 완료 PDF가 없으면 `total_pages=0`, `progress_percent=null`이다. 수강 완료 상태와 열람률은 별개다.

## 추가 질문과 상태 확인

`/ask`는 분석이 끝난 현재 페이지에 대해 질문하고 앞 대화를 이어 갈 수 있는 API다.

| API | 입력 | 성공 | 추가 오류 |
| --- | --- | --- | --- |
| `POST /documents/{document_id}/pages/{page_number}/ask` | `{question: string}` | `200 StoredChatExchange` | `404` 결과·페이지 없음, `409` 업로드·추출 미완료 또는 제외 페이지, `422` 페이지 범위·질문 길이 오류, `503` 설정 없음·DB 저장 실패, `502` 생성 실패 |
| `GET /documents/{document_id}/pages/{page_number}/chat` | 쿼리 `limit: 1~50`, 기본 `20` | `200 {document_id: UUID, page_number: number, exchanges: StoredChatExchange[]}` | `409` 업로드·추출 미완료, `422` 페이지 범위·limit 오류 |
| `GET /health` | 없음. 인증 불필요, `/api/v1` 밖 | `200 {status: "ok"}` | API 프로세스 응답 확인용 |

```ts
type StoredChatExchange = {
  id: UUID;
  question: string;
  answer_status: "answered" | "conversation" | "insufficient_evidence";
  explanation: string;
  evidence_block_ids: string[];
  created_at: DateTime;
};
```

`question`은 앞뒤 공백을 제거한 뒤 1~1,000자다. 서버가 같은 사용자·문서·페이지의 최근 3쌍을
오래된 순서로 Gemini에 전달한다. 기존 클라이언트가 보내는 `history`는 무시한다.
질문·답변을 DB에 함께 저장한 뒤 `200`을 반환하며 인사나 근거 부족 응답도 저장한다.
Gemini 호출·검증이 실패하면 대화 기록을 만들지 않는다.

```json
{
  "question": "그게 왜 필요한 거야?"
}
```

페이지에 진입하면 `/chat?limit=20`을 조회하고 `exchanges`를 그대로 표시한다. 최근 20쌍을 골라
그 안에서 오래된 순서로 반환하며 내역이 없으면 빈 배열이다. 최대 50쌍까지 조회할 수 있고,
그 이전 내역을 넘겨 보는 페이지네이션은 없다. DB에는 더 오래된 대화도 남지만 Gemini에는 최근 3쌍만 사용한다.
배포 전에 나눈 대화는 저장되어 있지 않아 복원되지 않는다.

전송 중에는 같은 페이지의 추가 전송을 막는다. 동시에 보낸 요청은 서로의 답변을 아직 참조할 수 없다.
성공 응답은 `id` 기준으로 화면 목록에 추가하고, 페이지를 바꾼 뒤 늦게 온 응답은 현재 화면에 붙이지 않는다.
전송 결과를 받지 못했다면 먼저 `/chat`을 다시 조회한다. 이미 저장된 질문을 재전송하면 새 대화로 저장된다.

`answered`에는 현재 페이지의 근거 블록이 한 개 이상 들어간다. `conversation`은 인사·감사 같은 짧은 대화이고,
`insufficient_evidence`는 현재 페이지에서 답을 뒷받침할 내용을 찾지 못한 경우다. 두 경우 모두 근거 목록은 비어 있으며
화면은 `explanation`을 그대로 표시한다. 근거가 있으면 기존 `/learning.evidence_blocks`에서 같은 `block_id`를 찾아 강조한다.
서버는 해당 페이지의 텍스트·표로 Gemini를 호출한다. `/chat` 조회 자체는 Gemini 호출이나 열람 진도 변경을 하지 않는다.
`/health` 성공은 DB·S3·워커·Gemini 상태까지 보장하지 않는다.

## 화면 연결 순서

1. 로그인 후 `/curricula`로 커리큘럼을 고르고 `/curricula/{id}/map`으로 과목·관계·수강 상태를 그린다.
   내 과목 목록은 `/courses/me`, 선택한 과목의 PDF는 `/documents?course_id=<UUID>`를 사용한다.
2. PDF는 URL 발급, S3 PUT, `/complete` 순서로 등록한다. 이후 `/file-url`로 바로 보여 주고 상태를 폴링한다.
3. 문서를 다시 열 때는 `/file-url`, `/progress`, `/status`를 조회한다. 마지막 페이지를 복원하고 실제 표시된 페이지를 PUT한다.
   페이지 수 미확정으로 `409`를 받으면 추출 후 현재 페이지를 기록한다.
4. 분석 완료 시 현재 페이지 `/learning`을 조회한다. 페이지 이동 시 해당 페이지의 `/learning`·`/note`·`/chat`을 읽고 진도를 PUT한다.
   분석 중에는 생성 중 안내, 완료됐지만 제외된 페이지에는 질문 없는 페이지 안내를 구분한다.
5. 질문 저장·해제 후에는 현재 `/learning`, 질문 목록, 저장 목록의 같은 UUID에 `is_saved`를 반영하거나 다시 조회한다.
   수강 상태를 바꾸면 지도·내 과목·추천 과목의 상태도 갱신한다.
6. PDF 전체 질문 화면은 `/documents/{id}/questions`, 저장함은 `/questions`를 쓴다.
   저장함에서 선택하면 `document_id`와 `page_number`로 해당 PDF 위치를 연다.
   PDF 삭제 후에는 문서 목록·저장함·과목 진도를 다시 조회한다.
