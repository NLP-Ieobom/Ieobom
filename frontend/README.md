# 이어봄 프론트엔드

React 19, TypeScript, Vite 기반 강의자료 학습 화면입니다. 배포된 백엔드의 실제 API 응답을 표시합니다.

## 실행

프로젝트 경로는 저장소의 `frontend/`입니다. Node.js 22.13 이상을 사용합니다. 기본 패키지 관리자는 `package.json`에 지정한 pnpm입니다.

```sh
cd frontend
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

기본 개발 주소는 `http://localhost:8443`입니다. npm 환경에서는 함께 제공한 `package-lock.json`으로 `npm ci` 후 `npm run dev`를 사용할 수 있습니다. 의존성 변경 시 사용한 잠금 파일과 다른 패키지 관리자의 잠금 파일을 함께 확인하세요.

## 화면과 데이터

- 워크스페이스: 과목별 PDF 목록·업로드·삭제, 최근 자료 이어보기
- PDF 뷰어: 페이지 이동·확대·축소, 근거 박스 좌표에 연결한 질문 마커
- 오른쪽 패널: 페이지 메모, 발견 질문의 간단한 답, 페이지별 AI 대화
- 더 깊이 알아보기: 관련 개념과 단계별 학습 정보를 보여주는 전체 페이지
- 저장한 질문: 목록·저장 해제·원문 이동·심화 학습
- 커리큘럼 맵: 교육과정별 과목·관계와 수강 상태

`analysis.summary`는 선택한 질문의 간단한 답에, `analysis.concepts`는 심화 학습 화면에 사용합니다. 현재 API에서 analysis는 페이지 단위이므로 같은 페이지의 질문은 summary를 공유합니다.

최근 PDF 3개는 계정별 ID 목록으로 이 브라우저의 localStorage에 보관합니다. 마지막 열람 페이지와 메모·질문 저장 상태는 서버 API를 사용합니다. 인증 정보는 sessionStorage에 저장합니다. 최근 목록에 파일 본문이나 인증 토큰을 넣지 않습니다.

## 백엔드 연결

개발 시 Vite 프록시, Vercel 배포 시 `vercel.json`의 rewrite가 다음 경로를 전달합니다.

- `/api/v1/*` → `https://13-209-160-89.sslip.io/api/v1/*`
- `/pdf-file/*` → `https://ieobom-materials.s3.amazonaws.com/*`

다른 API 서버를 사용하려면 `VITE_API_BASE_URL`을 설정하고 다시 빌드합니다. `VITE_` 변수는 브라우저에 공개되므로 비밀키를 넣지 마세요. S3 업로드에는 버킷의 CORS 설정이 필요합니다.

## 검증

```sh
corepack pnpm typecheck
corepack pnpm test
corepack pnpm build
```

npm에서는 `npm run typecheck`, `npm test`, `npm run build`를 사용합니다. 기본 테스트는 로컬 단위·서버 렌더링 테스트이며 실제 배포 서버를 변경하지 않습니다. `tests/api-integration.browser.mjs`는 별도의 Playwright 설치가 필요한 선택적 브라우저 테스트입니다.

## Git에 포함하는 파일

`src/`, `public/`, `tests/`, 빌드·배포 설정, 문서와 잠금 파일을 포함합니다. 빌드가 읽는 `.figma/make/site.json`도 반드시 포함합니다.

`node_modules/`, `dist/`, 환경 변수, `.vercel/`, `review/` 비교용 백업과 Figma 로컬 실행 도구는 제외합니다. 원본 이미지 파일은 로컬에 보관하고, 앱이 사용하는 `src/assets/question-marker.png`를 포함합니다. 제외 규칙은 `.gitignore`에 정의합니다.

Vercel 설정과 Git 반영 절차는 [DEPLOYMENT.md](DEPLOYMENT.md), 코드 기준 API 연동 범위는 [BACKEND_GAPS.md](BACKEND_GAPS.md)를 참고하세요.
