# Vercel 배포와 Git 반영

## 프로젝트 설정

Vercel 프로젝트가 다음 저장소와 디렉터리를 사용하도록 설정합니다.

| 항목 | 값 |
| --- | --- |
| GitHub 저장소 | `NLP-Ieobom/Ieobom` |
| Root Directory | `frontend` |
| Framework | Vite |
| Build Command | `npm run build` (`vercel.json`) |
| Output Directory | `dist` |
| Production Branch | 실제 운영에 사용할 브랜치 확인. 현재 로컬 브랜치는 `main` |

`package.json`의 packageManager는 `pnpm@10.34.3`입니다. Install Command를 수동 지정했다면 이 설정과 맞는지 확인하세요. 로컬 npm 검증용 `package-lock.json`도 포함합니다.

`vercel.json`은 API와 PDF 파일 프록시 경로도 정의합니다. 빌드에는 `.figma/make/site.json`이 필요합니다. 기본 백엔드 주소를 사용할 때 별도 프론트엔드 환경 변수는 필요하지 않습니다.

이 파일은 Vercel의 실제 Git 연결, 운영 브랜치, 도메인 또는 접근 보호 설정을 변경하지 않습니다. 자동 배포가 연결된 경우 push가 배포를 유발할 수 있으므로 프로젝트 대시보드에서 연결 상태를 확인하세요.

## 업로드 전 확인

저장소 루트에서 실행합니다.

```sh
cd frontend
npm run typecheck
npm test
npm run build
cd ..
git status --short
git status --short --untracked-files=all -- frontend
```

환경 변수, 인증 정보, 강의자료 PDF 원본, `node_modules/`, `dist/`, `review/`와 로컬 Figma 실행 도구가 포함되지 않는지 확인합니다. `.gitignore`가 업로드 대상을 정리하며 파일을 삭제하지 않습니다.

## 사용자가 직접 Git에 반영할 때

아래 명령은 준비 절차와 별개이며, 실제 반영을 결정한 후 실행합니다.

```sh
git add README.md frontend
git diff --cached --stat
git diff --cached --check
git commit -m "feat: add connected learning workspace frontend"
git push origin main
```

`git add` 이후에는 `git diff --cached`로 실제 반영 내용을 검토할 수 있습니다. Vercel이 GitHub 저장소와 해당 브랜치에 연결돼 있다면 push 이후 배포 내역에서 빌드 성공 여부와 적용 커밋을 확인합니다. Git 연결이 없다면 push만으로 배포되지는 않습니다.

## 배포 후 수동 확인

로그인 → 워크스페이스 → PDF 업로드·열람 → 질문 마커 → 심화 학습·원문 이동 → 저장한 질문 → 커리큘럼 맵 순서로 확인합니다. S3 업로드에는 실제 프론트엔드 Origin에 맞는 버킷 CORS가 필요합니다. 접근 보호와 공유 범위는 Vercel 대시보드에서 관리합니다.
