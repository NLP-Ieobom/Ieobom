import { readRecentDocuments, rememberDocument } from "./recentDocuments"
import { authenticate, getMe, hasSession, logout as apiLogout, listDocuments, uploadDocument, getFileUrl, getDocumentStatus, listMyCourses, getPageNote, savePageNote, listPageQuestions, listSavedQuestions, setQuestionSaved, listCurricula, getCurriculumMap, setEnrollment, removeEnrollment, getReadingProgress, recordPageView, retryAnalysis, deleteDocument, listDocumentQuestions, getPageLearning, getPageChat, askAboutPage, ApiError, type Curriculum, type CurriculumMapData, type EnrollmentStatus, type PageLearningData, type ChatExchange, type Question, type User, type Document, type DocumentStatus, type DocumentProgress, type ReadingProgress } from "./api"
const PdfReader = lazy(() => import("./PdfReader"))
import { keyboardPdfPage } from "./pdfNavigation"
import { documentState } from "./documentState"
import { learningQuestions, questionLabels, safeExternalUrl } from "./learningData"
import type { CourseConnections } from "./courseConnections"
import { createContext, useContext, lazy, Suspense, useMemo, useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react"

type IconName = "book" | "spark" | "map" | "chart" | "search" | "bell" | "chevron" | "arrow" | "bookmark" | "check" | "play" | "file" | "code" | "clock" | "external" | "zoomIn" | "zoomOut" | "layers" | "brain" | "database" | "wand" | "note" | "chat" | "send"

function Icon({
  name,
  size = 18,
  strokeWidth = 1.8,
}: {
  name: IconName
  size?: number
  strokeWidth?: number
}) {
  const paths: Record<IconName, ReactNode> = {
    book: (
      <>
        <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5z" />
        <path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z" />
      </>
    ),
    spark: (
      <>
        <path d="m12 3-1.1 3.2A7 7 0 0 1 6.5 10L3 11l3.5 1.1a7 7 0 0 1 4.4 4.1L12 20l1.1-3.8a7 7 0 0 1 4.4-4.1L21 11l-3.5-1a7 7 0 0 1-4.4-3.8z" />
        <path d="m19 3-.3 1a2.7 2.7 0 0 1-1.7 1.7L16 6l1 .3A2.7 2.7 0 0 1 18.7 8l.3 1 .3-1A2.7 2.7 0 0 1 21 6.3L22 6l-1-.3A2.7 2.7 0 0 1 19.3 4z" />
      </>
    ),
    map: (
      <>
        <path d="m3 6 5-3 8 3 5-3v15l-5 3-8-3-5 3z" />
        <path d="M8 3v15M16 6v15" />
      </>
    ),
    chart: (
      <>
        <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-4-4" />
      </>
    ),
    bell: (
      <>
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
        <path d="M10 21h4" />
      </>
    ),
    chevron: <path d="m9 18 6-6-6-6" />,
    arrow: (
      <>
        <path d="M5 12h14" />
        <path d="m14 7 5 5-5 5" />
      </>
    ),
    bookmark: <path d="M6 3h12v18l-6-4-6 4z" />,
    check: <path d="m5 12 4 4L19 6" />,
    play: <path d="m8 5 11 7-11 7z" />,
    file: (
      <>
        <path d="M6 2h8l4 4v16H6z" />
        <path d="M14 2v5h5M9 12h6M9 16h6" />
      </>
    ),
    code: (
      <>
        <path d="m8 9-4 3 4 3M16 9l4 3-4 3M14 5l-4 14" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    external: (
      <>
        <path d="M14 4h6v6M20 4l-9 9" />
        <path d="M18 13v7H4V6h7" />
      </>
    ),
    zoomIn: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 5 5M10.5 7.5v6M7.5 10.5h6" />
      </>
    ),
    zoomOut: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 5 5M7.5 10.5h6" />
      </>
    ),
    layers: (
      <>
        <path d="m12 3 9 5-9 5-9-5z" />
        <path d="m3 12 9 5 9-5M3 16l9 5 9-5" />
      </>
    ),
    brain: (
      <>
        <path d="M9.5 4.5A3 3 0 0 0 4 6a3 3 0 0 0 .5 5.5A3 3 0 0 0 7 17h2.5zM14.5 4.5A3 3 0 0 1 20 6a3 3 0 0 1-.5 5.5A3 3 0 0 1 17 17h-2.5z" />
        <path d="M9.5 4.5v15M14.5 4.5v15M7 8h2.5M14.5 12H18" />
      </>
    ),
    database: (
      <>
        <ellipse cx="12" cy="5" rx="8" ry="3" />
        <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
      </>
    ),
    wand: (
      <>
        <path d="m15 4 5 5L8 21l-5-5zM14 5l5 5" />
        <path d="M6 4V2M5 3H3M20 17v-2M19 16h-2" />
      </>
    ),
    note: (
      <>
        <path d="M5 3h14v18H5z" />
        <path d="M8 8h8M8 12h8M8 16h5" />
      </>
    ),
    chat: (
      <>
        <path d="M4 5h16v12H9l-5 4z" />
        <path d="M8 9h8M8 13h5" />
      </>
    ),
    send: (
      <>
        <path d="m3 11 18-8-8 18-2-8z" />
        <path d="m11 13 5-5" />
      </>
    ),
  }
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  )
}

type CourseMaterial = {
  documentId: string
  id: string
  course: string
  title: string
  fileName: string
  meta: string
  week: string
  color: string
  readingProgress?: Omit<DocumentProgress, "document_id">
}

function LoginScreen({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState("")
  const [mode, setMode] = useState<"login" | "signup">("login")
  const [busy, setBusy] = useState(false)
  const [passwordConfirm, setPasswordConfirm] = useState("")
  const changeMode = (next: "login" | "signup") => {
    if (busy) return
    setMode(next); setError(""); setPassword(""); setPasswordConfirm(""); setShowPassword(false)
  }
  return <main className="login-page">
    <section className="login-story" aria-label="이어봄 소개">
      <img className="login-logo" src="/logo/ieobom-final.png" alt="이어봄" />
      <div className="login-story-copy"><span className="eyebrow">LEARN. CONNECT. GO BEYOND.</span><h1>배움과 배움 사이,<br />새로운 가능성을<br /><em>이어봄.</em></h1><p>한 장의 강의자료에서 시작해<br />질문으로 깊어지고, 연결로 넓어지는 공부.</p></div>
      <div className="login-map-art" aria-hidden="true"><svg viewBox="0 0 460 190"><path d="M65 105 C135 105 150 50 230 50 S325 105 395 105 M230 50 C230 95 230 110 230 155" /></svg><span className="login-art-node art-ds"><Icon name="file" size={18} />강의자료</span><span className="login-art-node art-os"><Icon name="chat" size={20} />나의 질문<i>배움이 깊어지는 순간</i></span><span className="login-art-node art-cloud"><Icon name="spark" size={18} />더 넓은 이해</span><span className="login-art-dot" /></div>
      <small className="login-story-footer">작은 질문 하나가, 다음 배움의 시작이 되도록.</small>
    </section>
    <section className="login-form-panel">
      <div className="login-form-wrap">
        <span className="auth-eyebrow">YOUR LEARNING STARTS HERE</span>
        <div className="auth-tabs" role="group" aria-label="계정 접속 방식">
          <button type="button" aria-pressed={mode === "login"} disabled={busy} onClick={() => changeMode("login")}>로그인</button>
          <button type="button" aria-pressed={mode === "signup"} disabled={busy} onClick={() => changeMode("signup")}>회원가입</button>
        </div>
        <h2>{mode === "login" ? "다시 만나 반가워요" : "나의 배움을 시작해요"}<span className="auth-heading-dot">.</span></h2>
        <p className="login-subtitle">{mode === "login" ? "이어봄에서 지난 배움을 이어가세요." : "계정을 만들고, 새로운 배움을 이어가세요."}</p>
        <form aria-label={mode === "login" ? "로그인" : "회원가입"} aria-busy={busy} onSubmit={async (event) => {
          event.preventDefault()
          if (busy) return
          if (mode === "signup" && password !== passwordConfirm) { setError("비밀번호가 일치하지 않아요. 다시 확인해 주세요."); return }
          setBusy(true); setError("")
          try { const user = await authenticate(mode, email.trim(), password); setPassword(""); onLogin(user) }
          catch (error) { setError(error instanceof Error ? error.message : "로그인에 실패했어요.") }
          finally { setBusy(false) }
        }}>
          <label className="login-field" htmlFor="login-email">이메일<input id="login-email" type="email" autoComplete="username" placeholder="name@example.com" disabled={busy} required value={email} aria-describedby={error ? "login-error" : undefined} onChange={(event) => { setEmail(event.target.value); setError("") }} /></label>
          <label className="login-field" htmlFor="login-password">비밀번호<span className="login-password-wrap"><input id="login-password" type={showPassword ? "text" : "password"} minLength={mode === "signup" ? 8 : undefined} autoComplete={mode === "signup" ? "new-password" : "current-password"} placeholder={mode === "signup" ? "8자 이상 입력해 주세요" : "비밀번호를 입력해 주세요"} disabled={busy} required value={password} aria-describedby={error ? "login-error" : undefined} onChange={(event) => { setPassword(event.target.value); setError("") }} /><button type="button" aria-label={showPassword ? "비밀번호 숨기기" : "비밀번호 표시"} aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>{showPassword ? "숨김" : "표시"}</button></span></label>
          {mode === "signup" && <>
            <p className="auth-field-hint">비밀번호는 8자 이상으로 설정해 주세요.</p>
            <label className="login-field" htmlFor="signup-password-confirm">비밀번호 확인<input id="signup-password-confirm" type={showPassword ? "text" : "password"} autoComplete="new-password" placeholder="비밀번호를 한 번 더 입력해 주세요" required disabled={busy} value={passwordConfirm} aria-describedby={error ? "login-error" : undefined} onChange={(event) => { setPasswordConfirm(event.target.value); setError("") }} /></label>
          </>}
          {error && <p id="login-error" className="login-error" role="alert">{error}</p>}
          <button className="login-submit" type="submit" disabled={busy}>{busy ? "연결 중…" : mode === "signup" ? "회원가입" : "로그인"} <Icon name="arrow" size={17} /></button>
        </form>
        <p className="auth-switch">{mode === "login" ? "아직 계정이 없으신가요?" : "이미 계정이 있으신가요?"} <button type="button" disabled={busy} onClick={() => changeMode(mode === "login" ? "signup" : "login")}>{mode === "login" ? "회원가입" : "로그인"}<Icon name="arrow" size={13} /></button></p>
        <div className="auth-footer"><Icon name="book" size={15} /><span>작은 질문에서 시작하는, 나만의 학습 공간</span></div>
      </div>
    </section>
  </main>
}

function ProfileMenu({ user, onLogout, compact = false }: { user: User; onLogout: () => void; compact?: boolean }) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const logoutRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (!open) return
    const closeOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !containerRef.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener("pointerdown", closeOutside)
    return () => document.removeEventListener("pointerdown", closeOutside)
  }, [open])
  return <div className={`profile-menu ${compact ? "profile-menu-mobile" : ""}`} ref={containerRef} onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false) }} onKeyDown={(event) => {
    if (event.key === "Escape") { setOpen(false); triggerRef.current?.focus() }
  }}>
    <button ref={triggerRef} className="profile profile-trigger" aria-expanded={open} aria-label="사용자 메뉴" onClick={() => setOpen(!open)} onKeyDown={(event) => { if (event.key === "ArrowDown") { event.preventDefault(); setOpen(true); requestAnimationFrame(() => logoutRef.current?.focus()) } }}>
      <span className="avatar">봄</span><span className="profile-copy"><strong>{user.email}</strong><small>나의 학습 공간</small></span><Icon name="chevron" size={15} />
    </button>
    {open && <div className="profile-dropdown"><button ref={logoutRef} onClick={onLogout}>로그아웃 <Icon name="external" size={14} /></button></div>}
  </div>
}


const DeepLearningContext = createContext<(question: Question, onOpenSource?: () => void) => void>(() => {})

function AppShell({ user, view, onOpenMap, onOpenSavedQuestions, selectedCourse, selectedMaterial, onOpenWorkspace, onLogout, recentMaterials = [], onOpenRecent, children }: {
  user: User
  view: "workspace" | "map" | "saved"
  onOpenMap: () => void
  onOpenSavedQuestions: () => void
  selectedCourse: string | null
  selectedMaterial: CourseMaterial | null
  onOpenWorkspace: (course: string | null) => void
  onLogout: () => void
  recentMaterials?: CourseMaterial[]
  onOpenRecent?: (material: CourseMaterial) => void
  children: ReactNode
}) {
  const [deepQuestion, setDeepQuestion] = useState<Question | null>(null)
  const openSource = useRef<(() => void) | undefined>(undefined)
  useEffect(() => { setDeepQuestion(null) }, [view, selectedCourse, selectedMaterial])
  return <DeepLearningContext.Provider value={(question, onOpenSource) => { openSource.current = onOpenSource; setDeepQuestion(question) }}><div className="app-shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => { setDeepQuestion(null); onOpenWorkspace(null) }} aria-label="이어봄 홈"><img className="brand-logo" src="/logo/ieobom-final.png" alt="" /></button>
      <nav className="side-nav" aria-label="주요 화면">
        <p className="nav-eyebrow">MY LEARNING</p>
        <button className={`nav-item ${view === "workspace" ? "active" : ""}`} aria-current={view === "workspace" ? "page" : undefined} onClick={() => { setDeepQuestion(null); onOpenWorkspace(null) }}><span className="nav-icon"><Icon name="layers" size={19} /></span><span><strong>워크스페이스</strong><small>강의 자료와 AI 질문</small></span>{view === "workspace" && <span className="active-dot" />}</button>
        <button className={`nav-item ${view === "map" ? "active" : ""}`} aria-current={view === "map" ? "page" : undefined} onClick={() => { setDeepQuestion(null); onOpenMap() }}><span className="nav-icon"><Icon name="map" size={19} /></span><span><strong>커리큘럼 맵</strong><small>과목과 개념 연결</small></span>{view === "map" && <span className="active-dot" />}</button>
        <button className={`nav-item ${view === "saved" ? "active" : ""}`} aria-current={view === "saved" ? "page" : undefined} onClick={() => { setDeepQuestion(null); onOpenSavedQuestions() }}><span className="nav-icon"><Icon name="bookmark" size={19} /></span><span><strong>저장한 질문</strong><small>모아둔 질문 다시 보기</small></span>{view === "saved" && <span className="active-dot" />}</button>
      </nav>
      <section className="recent-section" aria-labelledby="recent-title"><div className="recent-heading"><p className="nav-eyebrow" id="recent-title">최근 공부한 페이지</p></div><div className="recent-list">{recentMaterials.map(material => <button key={material.documentId} className="recent-page" title={material.fileName} aria-label={`최근 PDF 열기: ${material.fileName}`} aria-current={selectedMaterial?.documentId === material.documentId ? "page" : undefined} onClick={() => { setDeepQuestion(null); onOpenRecent?.(material) }}><span className="recent-thumbnail"><Icon name="file" size={16} /></span><span className="recent-copy"><strong>{material.fileName}</strong><small>{material.course}</small></span><Icon name="chevron" size={13} /></button>)}{!recentMaterials.length && <p className="recent-empty">최근 열어본 PDF가 없어요.</p>}</div></section>
      <div className="sidebar-bottom"><ProfileMenu user={user} onLogout={onLogout} /></div>
    </aside>
    <main className="main">
      <header className="topbar">
        <div className="breadcrumb">
          <span>내 강의</span><i>/</i>
          {view === "map" ? <strong>커리큘럼 맵</strong> : view === "saved" ? <strong>저장한 질문</strong> : selectedMaterial ? <><button className="breadcrumb-link" onClick={() => onOpenWorkspace(selectedMaterial.course)}>{selectedMaterial.course}</button><i>/</i><span>문서 탐색</span></> : <strong>{selectedCourse ? `${selectedCourse} · PDF 선택` : "워크스페이스"}</strong>}
        </div>
        <div className="top-actions">
          <ProfileMenu user={user} onLogout={onLogout} compact />
        </div>
      </header>
      <div className="content"><div style={{ display: deepQuestion ? "none" : "contents" }}>{children}</div>{deepQuestion && <QuestionDeepDive key={deepQuestion.id} question={deepQuestion} onClose={() => setDeepQuestion(null)} onOpenSource={openSource.current ? () => { openSource.current?.(); setDeepQuestion(null) } : undefined} />}</div>
    </main>
  </div></DeepLearningContext.Provider>
}

type LearningPanelMode = "notes" | "questions" | "chat"
type PdfUploadHandler = (file: File, course: string) => Promise<void>
function UploadedPdfViewer({ material, initialPage, onProgress, onChanged }: { material: CourseMaterial; initialPage?: number; onProgress?: (id: string, progress: DocumentProgress) => void; onChanged?: () => void }) {
  const [page, setPage] = useState(initialPage ?? 1)
  const [pageCount, setPageCount] = useState(0)
  const [navigation, setNavigation] = useState({ page: initialPage ?? 1, sequence: 0 })
  const [renderedPage, setRenderedPage] = useState<number | null>(null)
  const [pageQuestions, setPageQuestions] = useState<Question[]>([])
  const [focusedQuestion, setFocusedQuestion] = useState<string | null>(null)
  const movePage = (next: number) => {
    const value = Math.max(1, Math.min(pageCount || 1, next))
    setRenderedPage(null); setPageQuestions([]); setFocusedQuestion(null)
    setPage(value); setNavigation(previous => ({ page: value, sequence: previous.sequence + 1 }))
  }
  const [zoom, setZoom] = useState(100)
  const [panelMode, setPanelMode] = useState<LearningPanelMode>("notes")
  const noteDrafts = useRef<Record<number, string>>({})
  const chatDrafts = useRef<Record<number, string>>({})
  const pendingChats = useRef(new Map<number, Promise<ChatExchange>>())
  const [url, setUrl] = useState("")
  const [status, setStatus] = useState<DocumentStatus | null>(null)
  const [error, setError] = useState("")
  const [progressError, setProgressError] = useState("")
  const [statusError, setStatusError] = useState("")
  const [retrying, setRetrying] = useState(false)
  const [retryError, setRetryError] = useState("")
  const [attempt, setAttempt] = useState(0)
  const [progressAttempt, setProgressAttempt] = useState(0)
  const callbacks = useRef({ onProgress, onChanged })
  callbacks.current = { onProgress, onChanged }
  const progressQueue = useRef<Promise<unknown>>(Promise.resolve())
  const lastRecordedPage = useRef<number | null>(null)
  const lastProgress = useRef<DocumentProgress | null>(null)
  useEffect(() => {
    let cancelled = false
    let fileTimer: ReturnType<typeof setTimeout> | undefined
    setError(""); setProgressError("")
    const loadFile = async () => {
      try {
        const result = await getFileUrl(material.documentId)
        if (cancelled) return
        setUrl(result.file_url)
        fileTimer = setTimeout(() => void loadFile(), Math.max(30, result.expires_in - 60) * 1000)
      } catch (error) { if (!cancelled) setError(error instanceof Error ? error.message : "PDF를 불러오지 못했어요.") }
    }
    const restore = async () => {
      try {
        const result = await getReadingProgress(material.documentId)
        if (cancelled) return
        const restoredPage = initialPage ?? result.last_page_number ?? 1
        setPage(restoredPage); setNavigation(previous => ({ page: restoredPage, sequence: previous.sequence + 1 }))
      } catch { if (!cancelled) setProgressError("마지막 열람 위치를 불러오지 못했어요.") }
      if (!cancelled) void loadFile()
    }
    void restore()
    return () => { cancelled = true; clearTimeout(fileTimer) }
  }, [material.documentId])
  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const poll = async () => {
      try {
        const result = await getDocumentStatus(material.documentId)
        if (cancelled) return
        const state = documentState(result)
        setStatus(result); setStatusError("")
        if (!state.terminal) timer = setTimeout(poll, 5000)
      } catch (error) { if (!cancelled) setStatusError(error instanceof Error ? error.message : "상태를 확인하지 못했어요.") }
    }
    void poll()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [material.documentId, attempt])
  useEffect(() => {
    if (!renderedPage) return
    let cancelled = false
    // Serialize writes so an earlier request cannot overwrite the last page.
    progressQueue.current = progressQueue.current.catch(() => {}).then(async () => {
      if (lastRecordedPage.current === renderedPage) {
        if (!cancelled && lastProgress.current) { setProgressError(""); callbacks.current.onProgress?.(material.documentId, lastProgress.current) }
        return
      }
      try {
        const result = await recordPageView(material.documentId, renderedPage)
        lastRecordedPage.current = renderedPage
        lastProgress.current = result
        if (!cancelled) { setProgressError(""); callbacks.current.onProgress?.(material.documentId, result) }
      } catch (error) {
        if (!cancelled) setProgressError(error instanceof ApiError && error.status === 409 ? "페이지 추출이 끝나면 열람 진도를 저장해요." : "열람 진도를 저장하지 못했어요.")
      }
    })
    return () => { cancelled = true }
  }, [material.documentId, renderedPage, status?.total_pages, progressAttempt])
  const retry = async () => {
    if (retrying) return
    setRetrying(true); setRetryError("")
    try { await retryAnalysis(material.documentId); setStatus(null); setAttempt(value => value + 1); callbacks.current.onChanged?.() }
    catch (error) { setRetryError(error instanceof Error ? error.message : "분석을 다시 시작하지 못했어요.") }
    finally { setRetrying(false) }
  }
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target instanceof HTMLElement ? event.target : null
      const editing = Boolean(target?.closest('input, textarea, select, [contenteditable="true"], [role="tablist"]'))
      const next = keyboardPdfPage(event, page, pageCount, editing)
      if (next === null) return
      event.preventDefault()
      if (next !== page) movePage(next)
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [page, pageCount])
  return <>
    <header className="page-header"><div><span className="eyebrow">LECTURE VIEWER · {material.course}</span><h1>{material.title}, 질문으로 깊게 읽기</h1><p>강의 자료의 핵심 맥락에서 발견한 질문을 따라 개념을 확장해 보세요.</p></div></header>
    <section className="viewer-layout" aria-label="업로드한 PDF">
    <div className="document-panel">
      <div className="panel-toolbar"><div className="file-info"><span className="pdf-badge">PDF</span><div><strong>{material.fileName}</strong><small>{material.course} · {status ? documentState(status).label : "상태 확인 중"}{status?.stage_progress_percent != null && ` ${status.stage_progress_percent}%`}</small></div></div>
        <div className="viewer-actions"><div className="page-controls"><button className="page-prev" aria-label="이전 슬라이드" disabled={!pageCount || page === 1} onClick={() => movePage(page - 1)}><Icon name="chevron" size={16} /></button><input aria-label="학습할 페이지" type="number" min="1" max={pageCount || 1} disabled={!pageCount} value={page} onChange={event => { const value = Number(event.target.value); if (Number.isInteger(value) && value > 0) movePage(value) }} /><span className="pdf-page-total">/ {pageCount || "—"}</span><button aria-label="다음 슬라이드" disabled={!pageCount || page >= pageCount} onClick={() => movePage(page + 1)}><Icon name="chevron" size={16} /></button></div>
          <button aria-label="축소" disabled={zoom <= 50} onClick={() => setZoom(value => Math.max(50, value - 10))}><Icon name="zoomOut" size={17} /></button><b>{zoom}%</b><button aria-label="확대" disabled={zoom >= 200} onClick={() => setZoom(value => Math.min(200, value + 10))}><Icon name="zoomIn" size={17} /></button>
          {url && <a href={url} target="_blank" rel="noreferrer" aria-label="PDF 새 창에서 열기"><Icon name="external" size={16} /></a>}
        </div>
      </div>
      {status?.error_message && <p className="analysis-notice" role="status">{status.error_message}</p>}
      {status?.next_retry_at && <p className="analysis-notice">자동 재시도 예정: {new Date(status.next_retry_at).toLocaleTimeString("ko-KR")}</p>}
      {status?.can_retry && <div className="analysis-notice"><span>{status.stage === "analysis_skipped" ? "질문 분석이 생략됐어요." : "분석을 다시 시도할 수 있어요."}</span><button disabled={retrying} onClick={() => void retry()}>{retrying ? "요청 중…" : "분석 다시 시도"}</button></div>}
      {retryError && <p className="document-load-error" role="alert">{retryError}</p>}
      {statusError && <p className="document-load-error" role="alert">{statusError}<button onClick={() => setAttempt(value => value + 1)}>상태 다시 확인</button></p>}
      {error && <p className="document-load-error" role="alert">{error}<button onClick={() => { setAttempt(value => value + 1); void getFileUrl(material.documentId).then(result => setUrl(result.file_url)).catch(error => setError(error.message)) }}>다시 시도</button></p>}
      {progressError && <p className="analysis-notice" role="status">{progressError}<button onClick={() => setProgressAttempt(value => value + 1)}>진도 다시 저장</button></p>}
      <div className="paper-stage live-pdf-stage">{url ? <Suspense fallback={<p role="status">PDF 뷰어를 불러오고 있어요.</p>}><PdfReader url={url} zoom={zoom} navigation={navigation} onPageChange={number => { setPage(number); setRenderedPage(number) }} onPageCount={setPageCount} questions={pageQuestions} onQuestionClick={question => { setPanelMode("questions"); setFocusedQuestion(question.id) }} /></Suspense> : !error && <p role="status">PDF를 불러오고 있어요.</p>}</div>
    </div>
    <PageLearning key={`${material.documentId}:${page}`} documentId={material.documentId} page={page} panelMode={panelMode} setPanelMode={setPanelMode} drafts={noteDrafts.current} chatDrafts={chatDrafts.current} pendingChats={pendingChats.current} analysisStatus={status} analysisAttempt={attempt} onQuestions={setPageQuestions} focusedQuestion={focusedQuestion} onNavigate={movePage} />
  </section></>
}


function WorkspacePicker({ courseIds, materials, loading, onSelect, courseLoading = false, courseError = "", onRetry, onOpenMaterial, onOpenMap, courseProgress = {}, courseStatuses = {}, recentDocumentIds = [] }: {
  courseIds: CourseConnections; materials: CourseMaterial[]; loading: boolean
  onSelect: (course: string) => void
  courseLoading?: boolean; courseError?: string; onRetry?: () => void; onOpenMaterial?: (material: CourseMaterial) => void
  onOpenMap?: () => void; courseProgress?: Record<string, ReadingProgress>; courseStatuses?: Record<string, EnrollmentStatus>; recentDocumentIds?: string[]
}) {
  const [query, setQuery] = useState("")
  const courses = Object.keys(courseIds)
  const materialById = new Map(materials.map(material => [material.documentId, material]))
  const recentMaterial = recentDocumentIds.map(id => materialById.get(id)).find(Boolean)
  const featuredMaterial = recentMaterial ?? materials.reduce<CourseMaterial | undefined>((latest, material) => !latest || (Date.parse(material.readingProgress?.last_viewed_at ?? "") || 0) > (Date.parse(latest.readingProgress?.last_viewed_at ?? "") || 0) ? material : latest, undefined)
  const lastPage = featuredMaterial?.readingProgress?.last_page_number
  const hasRecentMaterial = Boolean(recentMaterial || featuredMaterial?.readingProgress?.last_viewed_at)
  const statusOrder: Record<EnrollmentStatus, number> = { in_progress: 0, not_enrolled: 1, completed: 2 }
  const visible = courses.filter((course) => course.toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => statusOrder[courseStatuses[a] ?? "not_enrolled"] - statusOrder[courseStatuses[b] ?? "not_enrolled"])
  return <div className="workspace-home aligned-page-home">
    <header className="page-header"><div><span className="eyebrow">MY LEARNING SPACE</span><h1>워크스페이스<span>.</span></h1><p>내 과목과 강의자료를 한곳에서 확인하세요.</p></div></header>
    {featuredMaterial && onOpenMaterial && <button className="workspace-continue" onClick={() => onOpenMaterial(featuredMaterial)}><span className="continue-content"><span className="continue-label"><span />{hasRecentMaterial ? "최근 공부한 페이지" : "내 강의자료"}</span><strong>{featuredMaterial.course}</strong><span className="continue-topic">{featuredMaterial.title}{hasRecentMaterial && lastPage != null && ` · ${lastPage}페이지`}</span><span className="continue-action">{hasRecentMaterial ? "이어서 공부하기" : "강의자료 열기"}<Icon name="arrow" size={16} /></span></span><span className="continue-preview" aria-hidden="true"><span className="preview-sheet back" /><span className="preview-sheet"><span className="preview-code">PDF<Icon name="layers" size={20} /></span><strong>{featuredMaterial.title}</strong><span className="preview-rule" /><small>LECTURE NOTE</small></span></span></button>}
    <section className="workspace-collection" aria-label="과목별 워크스페이스">
      <div className="workspace-collection-heading"><h2>내 과목 <span>{courses.length}</span></h2><div className="workspace-collection-actions">{courses.length > 0 && <label className="workspace-search"><Icon name="search" size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="과목 검색" aria-label="워크스페이스 검색" /></label>}{onOpenMap && <button className="browse-courses" onClick={onOpenMap}>과목 찾아보기<Icon name="arrow" size={14} /></button>}</div></div>
      {courseLoading && <p role="status">과목을 불러오고 있어요.</p>}
      {courseError && <p role="alert">{courseError}<button onClick={onRetry}>다시 시도</button></p>}
      <div className="workspace-course-list">{visible.map((course) => <button className="workspace-course-row" key={course} onClick={() => onSelect(course)} style={{ "--subject-color": courseStatuses[course] === "completed" ? "#858b97" : `hsl(${(220 + courses.indexOf(course) * 137.508) % 360} 45% 62%)`, "--subject-bg": courseStatuses[course] === "completed" ? "#f0f1f3" : `hsl(${(220 + courses.indexOf(course) * 137.508) % 360} 65% 95%)` } as CSSProperties}>
        <span className="course-monogram" title={courseStatuses[course] === "completed" ? "수강 완료" : courseStatuses[course] === "in_progress" ? "수강 중" : undefined}><Icon name="book" size={21} /></span><span className="course-row-copy"><strong>{course}</strong><span>{courseProgress[course]?.progress_percent != null ? `자료 열람 ${courseProgress[course].progress_percent}%` : "연결된 강의자료 보기"}</span></span><span className="course-file-count"><Icon name="file" size={15} />{loading ? "확인 중" : `PDF ${materials.filter((item) => item.course === course).length}개`}</span><span className="course-row-arrow"><Icon name="arrow" size={17} /></span>
      </button>)}</div>
      {!courseLoading && !courseError && visible.length === 0 && <div className="library-empty"><Icon name="book" size={28} /><strong>{courses.length ? "검색 결과가 없어요" : "등록된 과목이 없어요"}</strong><p>{courses.length ? "다른 과목명으로 검색해 보세요." : ""}</p></div>}
    </section>

  </div>
}

function useQuestionAnalysis(question: Question, enabled: boolean) {
  const [analysis, setAnalysis] = useState(question.analysis)
  const [error, setError] = useState("")
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if (question.analysis) { setAnalysis(question.analysis); return }
    if (!enabled) return
    let cancelled = false
    setError("")
    getPageLearning(question.document_id, question.page_number).then(result => {
      if (!cancelled) setAnalysis(result.analysis)
    }).catch(() => { if (!cancelled) setError("답변 정보를 불러오지 못했어요.") })
    return () => { cancelled = true }
  }, [question.analysis, question.document_id, question.page_number, enabled, attempt])
  return { analysis, error, retry: () => setAttempt(value => value + 1) }
}

function QuestionDeepDive({ question, onClose, onOpenSource }: { question: Question; onClose: () => void; onOpenSource?: () => void }) {
  const { analysis, error, retry } = useQuestionAnalysis(question, true)
  const [openStep, setOpenStep] = useState(0)
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [])
  const steps: { title: string; icon: IconName; content: ReactNode }[] = [
    { title: "관련 개념", icon: "brain", content: <>{!analysis && !error && <p role="status">개념을 불러오고 있어요.</p>}{error && <p role="alert">{error}<button onClick={retry}>다시 시도</button></p>}{analysis && (analysis.concepts.length ? <div className="deep-concept-list">{analysis.concepts.map(concept => <span key={concept.name}>{concept.name}</span>)}</div> : <p>등록된 개념이 없어요.</p>)}</> },
    ...(question.prerequisite ? [{ title: "먼저 알아둘 지식", icon: "book" as IconName, content: <p>{question.prerequisite}</p> }] : []),
    ...(question.explanation ? [{ title: question.explanation.headline || "개념 이해하기", icon: "spark" as IconName, content: <><p>{question.explanation.body}</p><ol>{question.explanation.flow.map((step, index) => <li key={index}>{step}</li>)}</ol></> }] : []),
    ...(question.learning_order ? [{ title: "학습 순서", icon: "layers" as IconName, content: <p>{question.learning_order}</p> }] : []),
    ...(question.first_activity ? [{ title: "직접 해보기", icon: "play" as IconName, content: <p>{question.first_activity}</p> }] : []),
    ...((question.related_courses?.length || question.trends?.length) ? [{ title: "연관 과목과 연구로 확장하기", icon: "map" as IconName, content: <QuestionDetails question={{ ...question, explanation: null, prerequisite: "", learning_order: "", first_activity: "", recommended_reason: "" }} /> }] : []),
  ]
  return <div className="deep-learning-page">
    <div className="deep-page-actions"><button className="deep-back-button" onClick={onClose}>← 이전 화면으로</button><button className="evidence-button" disabled={!onOpenSource} onClick={onOpenSource}>원문 페이지 열기<Icon name="file" size={14} /></button></div>
    <header className="page-header"><div><span className="eyebrow">GUIDED LEARNING PATH</span><h1 ref={heading} tabIndex={-1}>질문에서 이해까지, 근거를 따라가요</h1><p>필요한 개념부터 학습과 탐구까지, 한 단계씩 깊이 있게 살펴보세요.</p></div></header>
    <div className="guide-layout">
      <section className="guide-question"><div className="guide-question-label"><Icon name="spark" size={16} />선택한 심화 질문</div><h2>{question.content}</h2><div className="guide-meta"><span>{question.page_number}페이지</span><i /><span>{questionLabels[question.question_type] ?? question.question_type}</span></div>{question.recommended_reason && <p className="deep-reason">{question.recommended_reason}</p>}</section>
      <div className="step-timeline">{steps.map((step, index) => <article key={step.title} className={`step-card ${openStep === index ? "open" : ""}`}><button className="step-summary" aria-expanded={openStep === index} aria-controls={`deep-step-${index}`} onClick={() => setOpenStep(openStep === index ? -1 : index)}><span className="step-number">{String(index + 1).padStart(2, "0")}</span><span className="step-icon"><Icon name={step.icon} size={20} /></span><span className="step-title"><small>STEP {index + 1}</small><strong>{step.title}</strong></span><span className="step-toggle">{openStep === index ? "−" : "+"}</span></button>{openStep === index && <div id={`deep-step-${index}`} className="step-content">{step.content}</div>}</article>)}</div>
    </div>
  </div>
}

function QuestionDetails({ question }: { question: Question }) {
  return <div className="question-detail">
    {question.explanation && <div className="question-explanation"><strong>{question.explanation.headline}</strong><p>{question.explanation.body}</p><ol>{question.explanation.flow.map((step, index) => <li key={index}>{step}</li>)}</ol></div>}
    {([["추천 이유", question.recommended_reason], ["선수 지식", question.prerequisite], ["학습 순서", question.learning_order], ["첫 활동", question.first_activity]]).map(([label, value]) => value && <p key={label}><strong>{label}</strong><br />{value}</p>)}
    {Boolean(question.related_courses?.length) && <section className="question-related"><h4>AI 추천 연관 과목</h4>{question.related_courses?.map(course => <div key={course.course_id}><strong>{course.name}</strong><small>{({ previous: "앞서 배우는 과목", next: "다음에 배우는 과목", related: "함께 살펴볼 과목" })[course.relation]}{course.enrollment_status && ` · ${{ not_enrolled: "미수강", in_progress: "수강 중", completed: "수강 완료" }[course.enrollment_status]}`}</small><p>{course.reason}</p>{course.next_topic && <p>다음 탐구: {course.next_topic}</p>}</div>)}</section>}
    {Boolean(question.trends?.length) && <section className="question-related"><h4>관련 연구와 탐구 방향</h4>{question.trends?.map(trend => <div key={trend.paper_id}><small>{trend.source === "gemini" ? "연구 방향 안내" : `관련 논문${trend.year ? ` · ${trend.year}` : ""}`}</small>{safeExternalUrl(trend.url) ? <a href={safeExternalUrl(trend.url)} target="_blank" rel="noreferrer">{trend.title}<Icon name="external" size={12} /></a> : <strong>{trend.title}</strong>}<p>{trend.summary}</p></div>)}</section>}
  </div>
}

function QuestionCard({ question, onChange, onOpen, compact = false, number = 1, selected = false }: { question: Question; onChange: (question: Question) => void; onOpen?: () => void; compact?: boolean; number?: number; selected?: boolean }) {
  const [answerOpen, setAnswerOpen] = useState(selected)
  const openDeepLearning = useContext(DeepLearningContext)
  const { analysis, error: answerError, retry: retryAnswer } = useQuestionAnalysis(question, answerOpen)
  useEffect(() => { if (selected) setAnswerOpen(true) }, [selected])
  const answer = <div className="question-brief-answer">{analysis?.summary ? <p>{analysis.summary}</p> : <p role="status">{answerError || "간단한 답을 불러오고 있어요."}</p>}{answerError && <button onClick={retryAnswer}>다시 시도</button>}<button className="evidence-button" onClick={() => openDeepLearning({ ...question, analysis }, onOpen)}>더 깊이 알아보기<Icon name="arrow" size={13} /></button></div>
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const toggle = async () => {
    setBusy(true); setError("")
    try { await setQuestionSaved(question.id, !question.is_saved); onChange({ ...question, is_saved: !question.is_saved }) }
    catch (error) { setError(error instanceof Error ? error.message : "질문을 저장하지 못했어요.") }
    finally { setBusy(false) }
  }
  if (compact) return <article className={`question-card ${question.is_saved ? "saved" : ""}`}>
    <div className="question-number">{String(number).padStart(2, "0")}</div><details className="question-body" open={answerOpen} onToggle={event => setAnswerOpen(event.currentTarget.open)}><summary><h3>{question.content}</h3><div className="tags"><span>{questionLabels[question.question_type] ?? question.question_type}</span><span>{question.page_number}페이지</span></div></summary>{answer}</details>
    <div className="question-actions"><button className="save-question" disabled={busy} aria-label={question.is_saved ? "저장한 질문에서 삭제" : "질문 저장"} aria-pressed={question.is_saved} onClick={() => void toggle()}><Icon name="bookmark" size={16} /></button></div>{error && <p role="alert">{error}</p>}
  </article>
  return <article className="learning-question"><small>{question.page_number}페이지 · {questionLabels[question.question_type] ?? question.question_type}</small><h3>{question.content}</h3>
    {answer}
    <button disabled={busy} aria-pressed={question.is_saved} onClick={() => void toggle()}>{busy ? "처리 중…" : question.is_saved ? "저장 해제" : "질문 저장"}</button>
    {onOpen && <button onClick={onOpen}>원문 페이지 열기</button>}{error && <p role="alert">{error}</p>}
  </article>
}

function PageLearning({ documentId, page, panelMode, setPanelMode, drafts, chatDrafts = {}, pendingChats = new Map(), analysisStatus = null, analysisAttempt = 0, onQuestions, focusedQuestion, onNavigate }: {
  documentId: string; page: number; panelMode: LearningPanelMode; setPanelMode: (mode: LearningPanelMode) => void; drafts: Record<number, string>
  chatDrafts?: Record<number, string>; pendingChats?: Map<number, Promise<ChatExchange>>; analysisStatus?: DocumentStatus | null; analysisAttempt?: number
  onQuestions?: (questions: Question[]) => void; focusedQuestion?: string | null
  onNavigate?: (page: number) => void
}) {
  const [questions, setQuestions] = useState<Question[]>([])
  const [allQuestions, setAllQuestions] = useState<Question[]>([])
  useEffect(() => { onQuestions?.(questions) }, [questions, onQuestions])
  useEffect(() => {
    if (!focusedQuestion || panelMode !== "questions") return
    setScope("page")
    const frame = requestAnimationFrame(() => {
      const card = document.getElementById(`discovered-question-${focusedQuestion}`)
      card?.scrollIntoView({ block: "nearest", behavior: "smooth" }); card?.focus({ preventScroll: true })
    })
    return () => cancelAnimationFrame(frame)
  }, [focusedQuestion, panelMode])
  const [learning, setLearning] = useState<PageLearningData | null>(null)
  const [scope, setScope] = useState<"page" | "document">("page")
  const [allLoading, setAllLoading] = useState(false)
  const [allError, setAllError] = useState("")
  const [note, setNote] = useState("")
  const [savedNote, setSavedNote] = useState("")
  const [loading, setLoading] = useState(true)
  const [noteReady, setNoteReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [learningError, setLearningError] = useState("")
  const [message, setMessage] = useState("")
  const [attempt, setAttempt] = useState(0)
  const [exchanges, setExchanges] = useState<ChatExchange[]>([])
  const [chatInput, setChatInput] = useState(chatDrafts[page] ?? "")
  const [chatLoading, setChatLoading] = useState(true)
  const [chatReady, setChatReady] = useState(false)
  const [chatBusy, setChatBusy] = useState(false)
  const [pendingQuestion, setPendingQuestion] = useState("")
  const [chatError, setChatError] = useState("")
  const [chatAttempt, setChatAttempt] = useState(0)
  const active = useRef(true)
  const messagesEnd = useRef<HTMLDivElement>(null)
  const analysisKey = `${analysisStatus?.job_status ?? ""}:${analysisStatus?.stage ?? ""}:${analysisAttempt}`
  const learningKey = `${analysisKey}:${analysisStatus?.completed_pages ?? 0}`
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  useEffect(() => {
    let cancelled = false
    setError(""); setNoteReady(false)
    getPageNote(documentId, page).then(result => {
      if (!cancelled) { setNote(drafts[page] ?? result.content ?? ""); setSavedNote(result.content ?? ""); setNoteReady(true) }
    }).catch(error => { if (!cancelled) setError(error instanceof ApiError && error.status === 409 ? "페이지 추출이 끝나면 메모를 사용할 수 있어요." : "메모를 불러오지 못했어요.") })
    return () => { cancelled = true }
  }, [documentId, page, attempt, analysisKey])
  useEffect(() => {
    let cancelled = false
    setLoading(true); setLearningError("")
    const load = async () => {
      try {
        const result = await getPageLearning(documentId, page)
        if (!cancelled) { setLearning(result); setQuestions(learningQuestions(documentId, result)) }
      } catch (error) {
        if (cancelled) return
        setLearning(null)
        if (!(error instanceof ApiError && [404, 409].includes(error.status))) setLearningError("학습 정보를 불러오지 못했어요.")
        try {
          const fallback = await listPageQuestions(documentId, page)
          if (!cancelled) setQuestions(fallback.questions)
        } catch { if (!cancelled) setQuestions([]) }
      } finally { if (!cancelled) setLoading(false) }
    }
    void load()
    return () => { cancelled = true }
  }, [documentId, page, attempt, learningKey])
  useEffect(() => {
    if (scope !== "document") return
    let cancelled = false
    setAllLoading(true); setAllError("")
    listDocumentQuestions(documentId).then(result => { if (!cancelled) setAllQuestions(result.questions) })
      .catch(() => { if (!cancelled) setAllError("PDF 전체 질문을 불러오지 못했어요.") }).finally(() => { if (!cancelled) setAllLoading(false) })
    return () => { cancelled = true }
  }, [documentId, scope, attempt, learningKey])
  useEffect(() => {
    let cancelled = false
    setChatLoading(true); setChatReady(false); setChatError("")
    const load = async () => {
      const pending = pendingChats.get(page)
      await pending?.catch(() => {})
      if (!cancelled && pending) setChatInput(chatDrafts[page] ?? "")
      try {
        const result = await getPageChat(documentId, page)
        if (!cancelled) { setExchanges(result.exchanges); setChatReady(true) }
      } catch (error) {
        if (!cancelled && !(error instanceof ApiError && error.status === 409)) setChatError("대화 내역을 불러오지 못했어요. 새로고침 후 다시 시도해 주세요.")
      } finally { if (!cancelled) setChatLoading(false) }
    }
    void load()
    return () => { cancelled = true }
  }, [documentId, page, chatAttempt, analysisKey])
  useEffect(() => { if (panelMode === "chat") messagesEnd.current?.scrollIntoView({ block: "nearest" }) }, [panelMode, exchanges, chatBusy])
  const save = async () => {
    setBusy(true); setMessage("")
    try { const result = await savePageNote(documentId, page, note); if (active.current) { setSavedNote(result.content ?? ""); delete drafts[page]; setMessage("메모를 저장했어요.") } }
    catch (error) { if (active.current) setMessage(error instanceof Error ? error.message : "메모 저장에 실패했어요.") }
    finally { if (active.current) setBusy(false) }
  }
  const updateQuestion = (updated: Question) => {
    setQuestions(items => items.map(item => item.id === updated.id ? updated : item))
    setAllQuestions(items => items.map(item => item.id === updated.id ? updated : item))
  }
  const send = async () => {
    const question = chatInput.trim()
    if (!question || question.length > 1000 || !chatReady || !learning?.analysis.question_eligible || pendingChats.has(page)) return
    setPendingQuestion(question); setChatBusy(true); setChatError("")
    const knownIds = new Set(exchanges.map(exchange => exchange.id))
    const pending = askAboutPage(documentId, page, question)
    pendingChats.set(page, pending)
    const accepted = () => { delete chatDrafts[page]; setChatInput("") }
    try {
      const result = await pending
      delete chatDrafts[page]
      if (active.current) { setExchanges(items => items.some(item => item.id === result.id) ? items : [...items, result]); accepted() }
    } catch (error) {
      if (!active.current) return
      // A lost response may already have been saved. Read history before allowing a resend.
      try {
        const result = await getPageChat(documentId, page)
        if (!active.current) return
        setExchanges(result.exchanges)
        if (result.exchanges.some(item => !knownIds.has(item.id) && item.question === question)) accepted()
        else setChatError(error instanceof ApiError && error.status === 503 ? "AI 답변을 지금 생성할 수 없어요. 잠시 후 다시 시도해 주세요." : "답변을 생성하지 못했어요. 다시 시도해 주세요.")
      } catch {
        if (active.current) { setChatReady(false); setChatError("전송 결과를 확인하지 못했어요. 대화 새로고침으로 내역을 확인해 주세요.") }
      }
    } finally { pendingChats.delete(page); if (active.current) setChatBusy(false) }
  }
  const visibleQuestions = scope === "document" ? allQuestions : questions
  const waiting = !analysisStatus || !documentState(analysisStatus).terminal
  const emptyTitle = scope === "page" && learning?.analysis.question_eligible === false
    ? "질문 생성 대상이 아닌 페이지예요"
    : waiting ? "질문을 분석하고 있어요"
    : analysisStatus?.job_status === "failed" ? "아직 분석을 마치지 못했어요"
    : analysisStatus?.stage === "analysis_skipped" ? "질문 분석이 생략됐어요" : "추천 질문이 없어요"
  const emptyDescription = scope === "page" && learning
    ? "다른 페이지의 질문도 살펴보세요."
    : waiting ? "완료된 페이지의 질문부터 자동으로 표시해요."
    : analysisStatus?.can_retry ? "분석을 다시 시도하면 완료된 부분에 이어서 진행해요." : "다른 페이지의 질문도 살펴보세요."
  const canChat = Boolean(learning?.analysis.question_eligible && chatReady && !chatLoading && !chatBusy)
  return <aside className="assistant-panel">
    <div className="assistant-tabs" role="tablist" aria-label="학습 도구">{([{ mode: "notes", icon: "note", label: "메모" }, { mode: "questions", icon: "spark", label: "발견 질문" }, { mode: "chat", icon: "chat", label: "AI 대화" }] as const).map(tab => <button key={tab.mode} id={`learning-tab-${tab.mode}`} aria-controls={`learning-panel-${tab.mode}`} className={panelMode === tab.mode ? "active" : ""} role="tab" aria-selected={panelMode === tab.mode} onClick={() => setPanelMode(tab.mode)}><Icon name={tab.icon} size={15} />{tab.label}{tab.mode === "questions" && questions.length > 0 && <i />}</button>)}</div>
    {error && <p className="document-load-error" role="alert">{error}<button onClick={() => setAttempt(value => value + 1)}>다시 시도</button></p>}
    {panelMode === "notes" && <div className="notes-view" role="tabpanel" id="learning-panel-notes" aria-labelledby="learning-tab-notes"><div className="assistant-head"><div className="ai-orb note-orb"><Icon name="note" size={19} /></div><div><span>MY LECTURE NOTES</span><h2>슬라이드 메모</h2></div></div>
      <div className="note-page-label"><span>PAGE {page}</span><small>{!noteReady ? "불러오는 중…" : busy ? "저장 중…" : note !== savedNote ? "저장하지 않은 변경" : ""}</small></div>
      <textarea className="note-editor" aria-label={`${page}페이지 메모`} disabled={!noteReady || busy} value={note} onChange={event => { drafts[page] = event.target.value; setNote(event.target.value); setMessage("") }} placeholder="이 슬라이드에서 기억할 내용을 자유롭게 적어보세요." />
      <div className="note-save-row"><span role="status">{message}</span><button disabled={!noteReady || busy || note === savedNote} onClick={() => void save()}>{busy ? "저장 중…" : "메모 저장"}</button></div>
      <div className="note-tip"><Icon name="spark" size={15} /><p><strong>학습 팁</strong>슬라이드의 핵심을 내 말로 한 문장씩 정리하면 오래 기억할 수 있어요.</p></div>
    </div>}
    {panelMode === "questions" && <div className="questions-view" role="tabpanel" id="learning-panel-questions" aria-labelledby="learning-tab-questions"><div className="assistant-head"><div className="ai-orb"><Icon name="spark" size={19} /></div><div><span>AI LEARNING ASSISTANT</span><h2>여기서 궁금할 만한 질문</h2></div></div>
      <div className={`context-chip ${questions.length ? "detected" : ""}`}><span className="pulse" />{page}페이지 · {loading ? "질문을 불러오고 있어요" : `발견한 질문 ${questions.length}개`}</div>
      <div className="question-scope" role="group" aria-label="질문 범위"><button aria-pressed={scope === "page"} onClick={() => setScope("page")}>현재 페이지</button><button aria-pressed={scope === "document"} onClick={() => setScope("document")}>PDF 전체 질문</button></div>
      {(learningError || allError) && <p role="alert">{learningError || allError}<button onClick={() => setAttempt(value => value + 1)}>다시 시도</button></p>}
      {scope === "document" && allLoading && <p role="status">전체 질문을 불러오고 있어요.</p>}
      {scope === "document" && waiting && visibleQuestions.length > 0 && <p role="status">완료된 페이지의 질문이에요. 나머지도 분석되는 대로 추가돼요.</p>}
      <div className="question-list">{visibleQuestions.map((question, index) => <div key={question.id} id={`discovered-question-${question.id}`} tabIndex={-1} className={focusedQuestion === question.id ? "question-marker-target" : undefined}><QuestionCard compact selected={focusedQuestion === question.id} number={index + 1} question={question} onChange={updateQuestion} onOpen={onNavigate ? () => onNavigate(question.page_number) : undefined} /></div>)}</div>
      {!loading && !allLoading && !learningError && !allError && !visibleQuestions.length && <div className="question-waiting"><span><Icon name="spark" size={22} /></span><strong>{emptyTitle}</strong><p>{emptyDescription}</p></div>}
      {learning?.research_status === "unavailable" && <p className="research-status">관련 연구 정보를 불러오지 못했어요.</p>}
    </div>}
    {panelMode === "chat" && <div className="chat-view" role="tabpanel" id="learning-panel-chat" aria-labelledby="learning-tab-chat"><div className="assistant-head"><div className="ai-orb"><Icon name="chat" size={19} /></div><div><span>AI LEARNING ASSISTANT</span><h2>AI와 함께 깊게 읽기</h2></div></div>
      <div className="chat-page-heading"><span>{page}페이지에 대한 대화</span><button disabled={chatLoading || chatBusy} onClick={() => setChatAttempt(value => value + 1)}>대화 새로고침</button></div>
      <div className="chat-messages" role="log" aria-label="페이지별 AI 대화" aria-live="polite">
        {chatLoading && <p role="status">이전 대화를 불러오고 있어요.</p>}
        {!chatLoading && !exchanges.length && <p className="chat-empty">{learning?.analysis.question_eligible ? "이 페이지에서 궁금한 내용을 물어보세요. 앞 대화를 이어서 질문할 수도 있어요." : learning?.analysis.question_eligible === false ? "이 페이지는 질문 생성 대상에서 제외됐어요. 다른 페이지에서 질문해 주세요." : "페이지 분석이 끝나면 질문할 수 있어요."}</p>}
        {exchanges.map(exchange => <div className="chat-exchange" key={exchange.id}><div className="chat-message user"><p>{exchange.question}</p></div><div className="chat-answer"><small>{exchange.answer_status === "insufficient_evidence" ? "현재 페이지의 근거가 부족해요" : exchange.answer_status === "conversation" ? "AI 응답" : "페이지를 바탕으로 한 답변"}</small><p>{exchange.explanation}</p></div></div>)}
        {chatBusy && <div className="chat-exchange chat-exchange-pending"><div className="chat-message user"><p>{pendingQuestion}</p></div><div className="chat-message assistant"><span className="chat-typing-avatar" aria-hidden="true"><Icon name="spark" size={15} /></span><div className="chat-typing-bubble" role="status" aria-label="AI가 답변을 작성하고 있어요"><span className="chat-typing-dots" aria-hidden="true"><i /><i /><i /></span></div></div></div>}<div ref={messagesEnd} />
      </div>
      {chatError && <p className="chat-error" role="alert">{chatError}</p>}
      <form className="chat-composer" onSubmit={event => { event.preventDefault(); void send() }}><textarea aria-label="AI에게 질문" placeholder="이 페이지에서 궁금한 점을 입력하세요" maxLength={1000} disabled={!canChat} value={chatInput} onChange={event => { chatDrafts[page] = event.target.value; setChatInput(event.target.value) }} /><button type="submit" aria-label="질문 보내기" disabled={!canChat || !chatInput.trim()}><Icon name="send" size={16} /></button></form>
      <p className="chat-disclaimer">{chatInput.length} / 1,000자 · 현재 페이지의 최근 대화를 참고해요.</p>
    </div>}
  </aside>
}

function SavedQuestionCard({ question, material, onRemove, onOpen }: { question: Question; material?: CourseMaterial; onRemove: () => void; onOpen?: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const openDeepLearning = useContext(DeepLearningContext)
  const { analysis, error: answerError, retry: retryAnswer } = useQuestionAnalysis(question, expanded)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const remove = async () => {
    setBusy(true); setError("")
    try { await setQuestionSaved(question.id, false); onRemove() }
    catch (error) { setError(error instanceof Error ? error.message : "저장을 해제하지 못했어요.") }
    finally { setBusy(false) }
  }
  return <article className="saved-question-item">
    <div className="saved-question-meta"><span>{material?.course ?? "강의자료"}</span><span>p.{question.page_number}</span><button disabled={busy} aria-label={`${question.content} 저장 해제`} title="저장 해제" onClick={() => void remove()}><Icon name="bookmark" size={17} /></button></div>
    <button className="saved-question-title" aria-expanded={expanded} aria-controls={`saved-question-detail-${question.id}`} onClick={() => setExpanded(value => !value)}><strong>{question.content}</strong><span>{expanded ? "−" : "+"}</span></button>
    {expanded && <div id={`saved-question-detail-${question.id}`} className="saved-question-answer"><p>{analysis?.summary || answerError || "간단한 답을 불러오고 있어요."}</p>{answerError && <button onClick={retryAnswer}>다시 시도</button>}</div>}
    {error && <p role="alert">{error}</p>}
    <footer><span><Icon name="file" size={14} />{material?.fileName ?? "강의자료"}</span><div className="saved-question-actions">{onOpen && <button onClick={onOpen}>원문에서 보기<Icon name="file" size={14} /></button>}<button className="saved-guide-button" onClick={() => openDeepLearning({ ...question, analysis }, onOpen)}>더 깊이 알아보기<Icon name="arrow" size={15} /></button></div></footer>
  </article>
}

function SavedQuestionsView({ materials = [], onOpen }: { materials?: CourseMaterial[]; onOpen?: (material: CourseMaterial, page: number) => void }) {
  const [query, setQuery] = useState("")
  const [course, setCourse] = useState("")
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let cancelled = false
    setLoading(true); setError("")
    listSavedQuestions().then(result => { if (!cancelled) setQuestions(result.questions) })
      .catch(error => { if (!cancelled) setError(error.message) }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [attempt])
  const visible = questions.filter(question => {
    const material = materials.find(item => item.documentId === question.document_id)
    return (!course || material?.course === course) && `${question.content} ${material?.course ?? ""}`.toLowerCase().includes(query.trim().toLowerCase())
  })
  return <div className="workspace-home saved-questions-home aligned-page-home">
    <header className="page-header"><div><span className="eyebrow">SAVED QUESTIONS</span><h1>저장한 질문<span>.</span></h1><p>다시 생각해 보고 싶은 질문, 원래 읽던 자료와 함께 이어보세요.</p></div></header>
    <div className="saved-questions-toolbar"><label className="library-search"><Icon name="search" size={17} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="질문 또는 과목 검색" aria-label="저장한 질문 검색" /></label><select aria-label="과목별 질문 필터" value={course} onChange={event => setCourse(event.target.value)}><option value="">전체 과목</option>{[...new Set(materials.map(item => item.course))].map(name => <option key={name}>{name}</option>)}</select><span>{visible.length}개의 질문</span></div>
    <section className="saved-question-list" aria-label="저장한 질문 목록">
      {loading && <p role="status">질문을 불러오고 있어요.</p>}{error && <p role="alert">{error}<button onClick={() => setAttempt(value => value + 1)}>다시 시도</button></p>}
      {!loading && !error && !visible.length && <div className="library-empty"><Icon name="bookmark" size={30} /><strong>{questions.length ? "검색 결과가 없어요" : "저장한 질문이 없어요"}</strong></div>}
      {visible.map(question => { const material = materials.find(item => item.documentId === question.document_id); return <SavedQuestionCard key={question.id} question={question} material={material} onRemove={() => setQuestions(items => items.filter(item => item.id !== question.id))} onOpen={material && onOpen ? () => onOpen(material, question.page_number) : undefined} /> })}
    </section>
  </div>
}

function mindMapLayout(ids: string[], relations: { source_course_id: string; target_course_id: string }[], selected: string | null) {
  if (selected && ids.includes(selected)) {
    const before = new Set<string>(), after = new Set<string>()
    for (const edge of relations) {
      if (edge.target_course_id === selected && edge.source_course_id !== selected && ids.includes(edge.source_course_id)) before.add(edge.source_course_id)
      if (edge.source_course_id === selected && edge.target_course_id !== selected && ids.includes(edge.target_course_id)) after.add(edge.target_course_id)
    }
    for (const id of before) after.delete(id)
    const leftColumns = Math.max(1, Math.ceil(before.size / 3)), rightColumns = Math.max(1, Math.ceil(after.size / 3))
    const width = Math.max(1000, (leftColumns + rightColumns + 1) * 270 + 80), height = 620
    const centerX = 40 + leftColumns * 270
    const positions = new Map<string, { x: number; y: number }>([[selected, { x: centerX, y: height / 2 - 72 }]])
    const branch = (items: Set<string>, side: number) => {
      const list = [...items]
      list.forEach((id, index) => {
        const column = Math.floor(index / 3), row = index % 3, count = Math.min(3, list.length - column * 3)
        positions.set(id, { x: centerX + side * (column + 1) * 270, y: height / 2 - (count * 180 - 36) / 2 + row * 180 })
      })
    }
    branch(before, -1); branch(after, 1)
    return { width, height, positions }
  }
  const next = new Map(ids.map(id => [id, new Set<string>()]))
  const incoming = new Map(ids.map(id => [id, 0]))
  for (const edge of relations) {
    const { source_course_id: from, target_course_id: to } = edge
    if (from === to || !next.has(from) || !next.has(to) || next.get(from)!.has(to)) continue
    next.get(from)!.add(to); incoming.set(to, incoming.get(to)! + 1)
  }
  const depths = new Map<string, number>()
  const queue = ids.filter(id => incoming.get(id) === 0)
  queue.forEach(id => depths.set(id, 0))
  for (let index = 0; index < queue.length; index++) {
    const id = queue[index]
    for (const child of next.get(id) ?? []) {
      depths.set(child, Math.max(depths.get(child) ?? 0, depths.get(id)! + 1))
      incoming.set(child, incoming.get(child)! - 1)
      if (incoming.get(child) === 0) queue.push(child)
    }
  }
  const layers = new Map<number, string[]>()
  ids.forEach(id => { const depth = depths.get(id) ?? 0; layers.set(depth, [...(layers.get(depth) ?? []), id]) })
  const ordered = [...layers].sort(([a], [b]) => a - b)
  const height = Math.max(620, Math.max(0, ...ordered.map(([, items]) => items.length)) * 180 + 80)
  const positions = new Map<string, { x: number; y: number }>()
  ordered.forEach(([, items], column) => items.forEach((id, row) => positions.set(id, { x: 40 + column * 320, y: (height - items.length * 180) / 2 + row * 180 + 18 })))
  return { width: Math.max(1000, ordered.length * 320 - 50), height, positions }
}

function CurriculumMap({ userId = "", onOpenCourse, onEnrollmentChanged }: { userId?: string; onOpenCourse?: (id: string, name: string) => void; onEnrollmentChanged?: () => void }) {
  const [curricula, setCurricula] = useState<Curriculum[]>([])
  const [curriculumId, setCurriculumId] = useState("")
  const [map, setMap] = useState<CurriculumMapData | null>(null)
  const [loadingMap, setLoadingMap] = useState(true)
  const [loadingCurricula, setLoadingCurricula] = useState(true)
  const [attempt, setAttempt] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const [courseQuery, setCourseQuery] = useState("")
  const [error, setError] = useState("")
  const [mutationError, setMutationError] = useState("")
  const [saving, setSaving] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [viewportWidth, setViewportWidth] = useState(900)
  const [viewportHeight, setViewportHeight] = useState(510)
  const canvasRef = useRef<HTMLDivElement>(null)
  const layout = useMemo(() => mindMapLayout((map?.courses ?? []).map(course => course.id), map?.relations ?? [], selected), [map, selected])
  const worldWidth = layout.width
  const worldHeight = layout.height
  const positions = layout.positions
  const zoomRef = useRef(zoom)
  const fitScaleRef = useRef(1)
  const zoomAnchor = useRef<{ x: number; y: number; clientX: number; clientY: number } | null>(null)
  zoomRef.current = zoom
  fitScaleRef.current = 1
  useLayoutEffect(() => {
    const canvas = canvasRef.current
    const bounds = canvas?.firstElementChild
    const anchor = zoomAnchor.current
    if (!canvas || !bounds || !anchor) return
    zoomAnchor.current = null
    const rect = bounds.getBoundingClientRect()
    const scale = fitScaleRef.current * zoom
    canvas.scrollLeft += rect.left + anchor.x * scale - anchor.clientX
    canvas.scrollTop += rect.top + anchor.y * scale - anchor.clientY
  }, [zoom])
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    let gestureStartZoom = 1
    let gesturing = false
    const zoomAt = (next: number, clientX: number, clientY: number) => {
      if (!Number.isFinite(next)) return
      const value = Math.max(.1, Math.min(2, next))
      if (value === zoomRef.current) return
      const bounds = canvas.firstElementChild?.getBoundingClientRect()
      if (!bounds) return
      const scale = bounds.width / worldWidth
      if (scale <= 0) return
      zoomAnchor.current = { x: (clientX - bounds.left) / scale, y: (clientY - bounds.top) / scale, clientX, clientY }
      zoomRef.current = value
      setZoom(value)
    }
    const wheel = (event: WheelEvent) => {
      // Trackpad pinch is delivered as Ctrl + wheel in Chromium and Firefox.
      if (!event.ctrlKey) return
      event.preventDefault()
      if (gesturing) return
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? canvas.clientHeight : 1)
      zoomAt(zoomRef.current * Math.exp(-delta * .01), event.clientX, event.clientY)
    }
    type PinchEvent = Event & { scale: number; clientX: number; clientY: number }
    const gestureStart = (event: Event) => {
      event.preventDefault()
      gesturing = true
      gestureStartZoom = zoomRef.current
    }
    const gestureChange = (event: Event) => {
      event.preventDefault()
      const pinch = event as PinchEvent
      if (gesturing) zoomAt(gestureStartZoom * pinch.scale, pinch.clientX, pinch.clientY)
    }
    const gestureEnd = (event: Event) => { event.preventDefault(); gesturing = false }
    canvas.addEventListener("wheel", wheel, { passive: false })
    // Safari exposes trackpad pinch through native gesture events instead.
    canvas.addEventListener("gesturestart", gestureStart, { passive: false })
    canvas.addEventListener("gesturechange", gestureChange, { passive: false })
    canvas.addEventListener("gestureend", gestureEnd, { passive: false })
    return () => {
      canvas.removeEventListener("wheel", wheel)
      canvas.removeEventListener("gesturestart", gestureStart)
      canvas.removeEventListener("gesturechange", gestureChange)
      canvas.removeEventListener("gestureend", gestureEnd)
    }
  }, [worldWidth])
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const observer = new ResizeObserver(([entry]) => { setViewportWidth(entry.contentRect.width); setViewportHeight(entry.contentRect.height) })
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [])
  useEffect(() => {
    let cancelled = false
    setLoadingCurricula(true); setError("")
    listCurricula().then(result => {
      if (cancelled) return
      setCurricula(result.curricula)
      setCurriculumId(previous => result.curricula.some(item => item.id === previous) ? previous : result.curricula[0]?.id ?? "")
    }).catch(error => { if (!cancelled) setError(error.message) }).finally(() => { if (!cancelled) setLoadingCurricula(false) })
    return () => { cancelled = true }
  }, [userId, attempt])
  useEffect(() => {
    if (!curriculumId) { setMap(null); setLoadingMap(false); return }
    let cancelled = false
    setLoadingMap(true); setMap(null); setError(""); setMutationError("")
    getCurriculumMap(curriculumId).then(result => {
      if (cancelled) return
      setMap(result); setSelected(previous => result.courses.some(course => course.id === previous) ? previous : null)
    }).catch(error => { if (!cancelled) setError(error.message) }).finally(() => { if (!cancelled) setLoadingMap(false) })
    return () => { cancelled = true }
  }, [curriculumId, attempt])
  const changeEnrollment = async (id: string, status: EnrollmentStatus) => {
    if (saving) return
    setSaving(true); setMutationError("")
    try {
      if (status === "not_enrolled") await removeEnrollment(id)
      else await setEnrollment(id, status)
      if (!active.current) return
      setMap(previous => previous ? { ...previous, courses: previous.courses.map(course => course.id === id ? { ...course, enrollment_status: status } : course) } : previous)
      onEnrollmentChanged?.()
    } catch (error) { if (active.current) setMutationError(error instanceof Error ? error.message : "수강 상태를 저장하지 못했어요.") }
    finally { if (active.current) setSaving(false) }
  }
  const scale = zoom
  const nodes = map?.courses ?? []
  useLayoutEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.scrollLeft = Math.max(0, (worldWidth * scale - canvas.clientWidth) / 2)
    canvas.scrollTop = Math.max(0, (worldHeight * scale - canvas.clientHeight) / 2)
  }, [selected, curriculumId, worldWidth, worldHeight, viewportWidth, viewportHeight])
  useEffect(() => { setZoom(1) }, [selected, curriculumId])
  const selectedNode = nodes.find(node => node.id === selected)
  const related = (map?.relations ?? []).filter(relation => relation.source_course_id === selected || relation.target_course_id === selected)
  const enrollmentLabel = { not_enrolled: "미수강", in_progress: "수강 중", completed: "수강 완료" }
  const relationLabel = (source: string, type: string) => ["demo", "ssu_2026_provisional"].includes(source) ? "시연용 학습 추천" : type === "prerequisite" ? "선수 관계" : type === "recommended" ? "학습 추천" : "과목 연결"
  return <div className="curriculum-home">
    <header className="page-header curriculum-page-heading"><div><span className="eyebrow">CURRICULUM KNOWLEDGE MAP</span><h1>커리큘럼 맵<span>.</span></h1><p>하나의 개념이 다음 과목으로 이어지는 흐름을 살펴보세요.</p></div></header>
    <section className="map-layout" aria-label="커리큘럼 맵">
      <div className="knowledge-map">
        <div className="map-toolbar"><label>교육과정 <select aria-label="교육과정 선택" value={curriculumId} disabled={loadingCurricula || saving || !curricula.length} onChange={event => setCurriculumId(event.target.value)}>{!curricula.length && <option value="">교육과정 선택</option>}{curricula.map(item => <option key={item.id} value={item.id}>{item.institution} · {item.department} · {item.entry_year}{item.is_demo ? " (시연용)" : ""}</option>)}</select></label><div className="map-course-picker"><input type="search" aria-label="맵 과목 검색" placeholder="다른 과목 찾아보기" value={courseQuery} onChange={event => setCourseQuery(event.target.value)} />{selected && <button onClick={() => { setSelected(null); setCourseQuery("") }}>전체 과목 보기</button>}{courseQuery.trim() && <div className="map-course-results">{nodes.filter(node => `${node.name} ${node.course_code ?? ""}`.toLowerCase().includes(courseQuery.trim().toLowerCase())).map(node => <button key={node.id} onClick={() => { setSelected(node.id); setCourseQuery("") }}>{node.name}{node.course_code && <small>{node.course_code}</small>}</button>)}{!nodes.some(node => `${node.name} ${node.course_code ?? ""}`.toLowerCase().includes(courseQuery.trim().toLowerCase())) && <p>검색 결과가 없어요.</p>}</div>}</div><span>{nodes.length}개 과목 · {map?.relations.length ?? 0}개 연결</span><div className="map-zoom-controls"><button aria-label="맵 축소" disabled={zoom <= .1} onClick={() => setZoom(value => Math.max(.1, +(value - .2).toFixed(1)))}><Icon name="zoomOut" size={16} /></button><button className="map-zoom-reset" aria-label="맵 화면에 맞추기" onClick={() => { setZoom(Math.min(1, (viewportWidth - 24) / worldWidth, (viewportHeight - 24) / worldHeight)); if (canvasRef.current) { canvasRef.current.scrollLeft = 0; canvasRef.current.scrollTop = 0 } }}>{Math.round(scale * 100)}%</button><button aria-label="맵 확대" disabled={zoom >= 2} onClick={() => setZoom(value => Math.min(2, +(value + .2).toFixed(1)))}><Icon name="zoomIn" size={16} /></button></div></div>
        {error && <p className="document-load-error" role="alert">{error}<button onClick={() => setAttempt(value => value + 1)}>다시 시도</button></p>}
        <div className="map-canvas" ref={canvasRef} tabIndex={0} aria-label="과목 연결 지도"><div className="map-scaled-bounds" style={{ width: worldWidth * scale, height: worldHeight * scale, marginTop: Math.max(0, (viewportHeight - worldHeight * scale) / 2) }}><div className="map-world" style={{ width: worldWidth, height: worldHeight, transform: `scale(${scale})` }}>
          {(loadingMap || loadingCurricula) && <p className="map-empty" role="status">과목을 불러오고 있어요.</p>}{!loadingMap && !loadingCurricula && !error && !nodes.length && <p className="map-empty">{curricula.length ? "등록된 과목이 없어요." : "등록된 교육과정이 없어요."}</p>}
          {related.length > 0 && <svg className="course-relations" width={worldWidth} height={worldHeight} role="img" aria-label="과목 간 학습 연결 관계"><defs><linearGradient id="course-connection-line" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2={worldWidth} y2="0"><stop stopColor="#3155d8" stopOpacity=".25" /><stop offset=".5" stopColor="#3155d8" /><stop offset="1" stopColor="#3155d8" stopOpacity=".25" /></linearGradient></defs>{related.map(relation => {
            const from = positions.get(relation.source_course_id), to = positions.get(relation.target_course_id)
            if (!from || !to) return null
            const emphasized = relation.source_course_id === selected
            const horizontal = Math.abs(to.x - from.x) >= Math.abs(to.y - from.y)
            const forward = horizontal ? to.x > from.x : to.y > from.y
            const start = horizontal ? { x: from.x + (forward ? 190 : 0), y: from.y + 72 } : { x: from.x + 95, y: from.y + (forward ? 144 : 0) }
            const end = horizontal ? { x: to.x + (forward ? 0 : 190), y: to.y + 72 } : { x: to.x + 95, y: to.y + (forward ? 0 : 144) }
            const middleX = (start.x + end.x) / 2, middleY = (start.y + end.y) / 2
            const curve = horizontal ? `M${start.x} ${start.y} C${middleX} ${start.y} ${middleX} ${end.y} ${end.x} ${end.y}` : `M${start.x} ${start.y} C${start.x} ${middleY} ${end.x} ${middleY} ${end.x} ${end.y}`
            return <g key={relation.id} ref={group => {
              const path = group?.querySelector("path")
              const dot = group?.querySelector("circle")
              if (!path || !dot) return
              const point = path.getPointAtLength(path.getTotalLength() / 2)
              dot.setAttribute("cx", String(point.x))
              dot.setAttribute("cy", String(point.y))
            }}><path className={emphasized ? "main-line" : "soft-line"} d={curve}><title>{relationLabel(relation.source, relation.relation_type)}</title></path>{emphasized && <circle cx={middleX} cy={middleY} r="4" />}</g>
          })}</svg>}
          {nodes.filter(node => positions.has(node.id)).map(node => { const position = positions.get(node.id)!; return <button key={node.id} style={{ left: position.x, top: position.y }} className={`map-node ${node.enrollment_status === "not_enrolled" ? "is-unenrolled" : "is-enrolled"} ${node.enrollment_status === "completed" ? "is-completed" : ""} ${selected === node.id ? "selected" : ""} ${selected && selected !== node.id && !related.some(edge => edge.source_course_id === node.id || edge.target_course_id === node.id) ? "is-context" : ""}`} title={node.name} aria-pressed={selected === node.id} onClick={() => { setSelected(previous => previous === node.id ? null : node.id); setCourseQuery("") }}><span><Icon name={node.enrollment_status === "completed" ? "check" : "book"} size={20} /></span><strong>{node.name}</strong><small>{enrollmentLabel[node.enrollment_status]}{node.reading_progress.progress_percent != null && ` · ${node.reading_progress.progress_percent}% 열람`}</small></button> })}
        </div></div></div>
        <div className="map-status-key"><span>미수강</span><span>수강 중</span><span>수강 완료</span></div>
      </div>
      <aside className="map-aside"><div className="selected-concept"><span className="eyebrow">SELECTED COURSE</span><div className="concept-icon"><Icon name="layers" size={22} /></div><div className="course-title-row"><h2>{selectedNode?.name ?? "과목 선택"}</h2></div>
        {selectedNode ? <><label className="enrollment-control">수강 상태<select aria-label="수강 상태" disabled={saving} value={selectedNode.enrollment_status} onChange={event => void changeEnrollment(selectedNode.id, event.target.value as EnrollmentStatus)}><option value="not_enrolled">미수강</option><option value="in_progress">수강 중</option><option value="completed">수강 완료</option></select></label>{saving && <p role="status">수강 상태를 저장하고 있어요.</p>}{mutationError && <p role="alert">{mutationError}</p>}<div className="skill-tags">{selectedNode.course_code && <span>{selectedNode.course_code}</span>}{selectedNode.curriculum_year && <span>{selectedNode.curriculum_year} 교육과정</span>}</div>{selectedNode.reading_progress.progress_percent != null && <p className="course-reading-progress">자료 열람 {selectedNode.reading_progress.progress_percent}%</p>}<button className="map-workspace-button" disabled={selectedNode.enrollment_status === "not_enrolled" || !onOpenCourse || saving} onClick={() => onOpenCourse?.(selectedNode.id, selectedNode.name)}>워크스페이스로 이동<Icon name="arrow" size={16} /></button></> : <p>맵에서 과목을 선택해 주세요.</p>}
      </div><div className="map-related-courses"><h3>연관 과목</h3><p>선택한 과목과 이어지는 학습 흐름이에요.</p>{related.map(relation => { const next = relation.source_course_id === selected; const target = nodes.find(node => node.id === (next ? relation.target_course_id : relation.source_course_id)); return target && <button className="related-course-row" key={relation.id} onClick={() => setSelected(target.id)}><strong>{target.name}</strong><span>{next ? "이후 학습" : "앞선 학습"} · {relationLabel(relation.source, relation.relation_type)}</span></button> })}{!related.length && <div className="map-related-empty">{selectedNode ? "등록된 연결 관계가 없어요." : "과목을 선택해 주세요."}</div>}</div></aside>
    </section>
  </div>
}

function WorkspaceLibrary({
  onSelect,
  course,
  materials: allMaterials,
  onUpload,
  onDelete,
}: {
  materials: CourseMaterial[]
  onUpload: PdfUploadHandler
  onSelect: (material: CourseMaterial) => void
  course: string
  onDelete?: (material: CourseMaterial) => Promise<void>
}) {
  const [query, setQuery] = useState("")
  const fileInput = useRef<HTMLInputElement>(null)
  const busyRef = useRef(false)
  const dragDepth = useRef(0)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState("")
  const [uploadError, setUploadError] = useState("")
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState("")
  const remove = async (material: CourseMaterial) => {
    if (!onDelete || deleting) return
    setDeleting(true); setDeleteError("")
    try { await onDelete(material); setDeleteTarget(null) }
    catch (error) { setDeleteError(error instanceof ApiError && error.status === 409 ? "분석이 끝난 뒤 PDF를 삭제할 수 있어요." : error instanceof Error ? error.message : "PDF를 삭제하지 못했어요.") }
    finally { setDeleting(false) }
  }
  const uploadFiles = async (files: File[]) => {
    if (!files.length || busyRef.current) return
    busyRef.current = true
    setUploading(true); setUploadMessage(""); setUploadError("")
    let added = 0
    const errors: string[] = []
    try {
      for (const file of files) {
        try {
          if (!file.name.toLowerCase().endsWith(".pdf")) throw new Error("PDF 파일만 업로드할 수 있어요.")
          if (file.size > 50 * 1024 * 1024) throw new Error("50MB 이하의 PDF를 선택해 주세요.")
          const header = new TextDecoder().decode(await file.slice(0, 1024).arrayBuffer())
          if (!header.includes("%PDF-")) throw new Error("올바른 PDF 파일인지 확인해 주세요.")
          await onUpload(file, course)
          added++
        } catch (error) { errors.push(`${file.name}: ${error instanceof Error ? error.message : "업로드하지 못했어요."}`) }
      }
      if (added) { setQuery(""); setUploadMessage(`PDF ${added}개를 추가했어요.`) }
      setUploadError(errors.join("\n"))
    } finally { busyRef.current = false; setUploading(false) }
  }
  const materials = allMaterials.filter((material) => material.course === course)
  const visibleMaterials = materials.filter((material) => `${material.title} ${material.fileName}`.toLowerCase().includes(query.toLowerCase()))

  return (
    <div className={`workspace-library${dragging ? " is-dragging" : ""}`}
      onDragEnter={(event) => {
        if (!Array.from(event.dataTransfer.types).includes("Files")) return
        event.preventDefault(); dragDepth.current++; setDragging(true)
      }}
      onDragOver={(event) => {
        if (!Array.from(event.dataTransfer.types).includes("Files")) return
        event.preventDefault(); event.dataTransfer.dropEffect = uploading ? "none" : "copy"
      }}
      onDragLeave={(event) => {
        event.preventDefault(); dragDepth.current = Math.max(0, dragDepth.current - 1)
        if (!dragDepth.current) setDragging(false)
      }}
      onDrop={(event) => {
        event.preventDefault(); dragDepth.current = 0; setDragging(false)
        void uploadFiles(Array.from(event.dataTransfer.files))
      }}>
      {dragging && <div className="pdf-drop-overlay"><Icon name="file" size={32} /><strong>{uploading ? "PDF를 추가하고 있어요" : "PDF를 여기에 놓으세요"}</strong><span>현재 과목에 추가돼요 · 파일당 최대 50MB</span></div>}
      <div className="library-heading">
        <div>
          <span className="eyebrow">MY LECTURE MATERIALS</span>
          <h1>{course ? `${course} 워크스페이스` : "어떤 강의자료를 이어볼까요?"}</h1>
          <p>업로드한 PDF를 선택해 열람하세요.</p>
        </div>
        <div className="library-summary">
          <span>
            <strong>{materials.length}</strong>
            등록된 자료
          </span>

        </div>
      </div>

      <div className="library-toolbar">
        <div className="library-search-upload">
        <label className="library-search">
          <Icon name="search" size={18} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="파일명으로 검색"
            aria-label="강의자료 검색"
          />
        </label>
        <button type="button" className="pdf-upload-button" disabled={uploading} onClick={() => fileInput.current?.click()}><Icon name="file" size={16} />{uploading ? "추가 중…" : "PDF 업로드"}</button>
        <input ref={fileInput} type="file" accept="application/pdf,.pdf" multiple hidden aria-label="업로드할 PDF 파일" onChange={(event) => {
          const files = Array.from(event.target.files ?? [])
          event.target.value = ""
          void uploadFiles(files)
        }} />
        </div>
      </div>

      <p className="pdf-drop-hint">PDF를 이 화면에 드래그해서 놓아도 추가할 수 있어요. · 파일당 최대 50MB · 서버에 저장</p>
      {uploadMessage && <p className="pdf-upload-status" role="status">{uploadMessage}</p>}
      {uploadError && <p className="pdf-upload-error" role="alert">{uploadError}</p>}
      {deleteError && <p className="pdf-upload-error" role="alert">{deleteError}</p>}
      <section className="material-grid" aria-label="강의자료 목록">
        {visibleMaterials.map((material, index) => (
          <article
            className={`material-card ${
              index === 0 && !query ? "featured" : ""
            }`}
            key={material.id}
          >
            <button className="material-open" onClick={() => onSelect(material)}>
            <div
              className="material-cover"
              style={{ "--cover-color": material.color } as CSSProperties}
            >
              <span className="material-week">{material.week}</span>
              <div className="cover-subject">
                <small>{material.course}</small>
                <strong>{material.title}</strong>
              </div>
              <span className="cover-number">0{index + 1}</span>
            </div>
            <div className="material-info">
              <div className="material-title">
                <span className="pdf-badge">PDF</span>
                <div>
                  <strong>{material.fileName}</strong>
                  <small>{material.meta}</small>
                </div>
              </div>
              <div className="material-bottom">
                <span className="new-material">{material.readingProgress?.progress_percent != null ? `${material.readingProgress.progress_percent}% 열람` : material.meta}</span>
                <span className="open-material">PDF 열기<Icon name="arrow" size={14} /></span>
              </div>
            </div>
            </button>
            {onDelete && <div className="material-manage">{deleteTarget === material.id ? <div className="delete-confirm" role="group" aria-label={`${material.fileName} 삭제 확인`}><p>PDF와 메모·질문·대화 기록을 삭제할까요?</p><button disabled={deleting} onClick={() => void remove(material)}>{deleting ? "삭제 중…" : "삭제 확인"}</button><button disabled={deleting} onClick={() => setDeleteTarget(null)}>취소</button></div> : <button aria-label={`${material.fileName} 삭제`} disabled={deleting} onClick={() => { setDeleteError(""); setDeleteTarget(material.id) }}>PDF 삭제</button>}</div>}
          </article>
        ))}
      </section>

      {visibleMaterials.length === 0 && (
        <div className="library-empty">
          <Icon name="file" size={28} />
          <strong>{query ? "검색 결과가 없어요" : "아직 등록된 PDF가 없어요"}</strong>
          <p>{query ? "다른 파일명으로 검색해 보세요." : "PDF를 업로드하면 이곳에 표시됩니다."}</p>
        </div>
      )}
    </div>
  )
}


function makeMaterial(document: Document, course: string): CourseMaterial {
  return { id: document.document_id, documentId: document.document_id, course,
    title: document.filename.replace(/\.pdf$/i, ""), fileName: document.filename,
    meta: document.status, week: new Date(document.created_at).toLocaleDateString("ko-KR"), color: "#3155d8", readingProgress: document.reading_progress }
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [checkingSession, setCheckingSession] = useState(hasSession)
  const [sessionError, setSessionError] = useState("")
  const [materials, setMaterials] = useState<CourseMaterial[]>([])
  const [courseIds, setCourseIds] = useState<CourseConnections>({})
  const [courseStatuses, setCourseStatuses] = useState<Record<string, EnrollmentStatus>>({})
  const [courseProgress, setCourseProgress] = useState<Record<string, ReadingProgress>>({})
  const [courseError, setCourseError] = useState("")
  const [loadingCourses, setLoadingCourses] = useState(false)
  const [recentIds, setRecentIds] = useState<string[]>([])
  const [initialPage, setInitialPage] = useState<number | undefined>(undefined)
  const [view, setView] = useState<"workspace" | "map" | "saved">("workspace")
  const [selectedCourse, setSelectedCourse] = useState<string | null>(null)
  const [selectedMaterial, setSelectedMaterial] = useState<CourseMaterial | null>(null)
  const [documentError, setDocumentError] = useState("")
  const [loadingDocuments, setLoadingDocuments] = useState(false)
  const [reload, setReload] = useState(0)
  const activeUser = useRef<string | null>(null)
  const reset = () => { setRecentIds([]); activeUser.current = null; setUser(null); setCourseIds({}); setCourseProgress({}); setCourseStatuses({}); setMaterials([]); setView("workspace"); setSelectedMaterial(null); setSelectedCourse(null) }
  const login = (value: User) => {
    try { setRecentIds(readRecentDocuments(localStorage.getItem(`ieobom-recent-pdfs:${value.id}`))) } catch { setRecentIds([]) }
    activeUser.current = value.id
    setUser(value)
    setView("workspace")
    setSelectedCourse(null); setSelectedMaterial(null); setSessionError("")
  }
  useEffect(() => {
    let cancelled = false
    window.addEventListener("ieobom-session-ended", reset)
    if (hasSession()) getMe().then((value) => { if (!cancelled) login(value) })
      .catch((error) => { if (!cancelled) setSessionError(error instanceof Error ? error.message : "로그인을 확인하지 못했어요.") })
      .finally(() => { if (!cancelled) setCheckingSession(false) })
    return () => { cancelled = true; window.removeEventListener("ieobom-session-ended", reset) }
  }, [])
  useEffect(() => {
    let cancelled = false
    setCourseError("")
    if (!user) { setCourseIds({}); setCourseProgress({}); setCourseStatuses({}); return }
    setLoadingCourses(true)
    listMyCourses().then(result => {
      if (cancelled) return
      const counts = new Map<string, number>()
      result.courses.forEach(course => counts.set(course.name, (counts.get(course.name) ?? 0) + 1))
      const entries = result.courses.map(course => ({ course, label: counts.get(course.name)! > 1 ? `${course.name} (${course.course_code ?? course.id})` : course.name }))
      setCourseIds(Object.fromEntries(entries.map(({ course, label }) => [label, course.id])))
      setCourseProgress(Object.fromEntries(entries.map(({ course, label }) => [label, course.reading_progress])))
      setCourseStatuses(Object.fromEntries(entries.map(({ course, label }) => [label, course.enrollment_status])))
    }).catch(error => { if (!cancelled) setCourseError(error.message) }).finally(() => { if (!cancelled) setLoadingCourses(false) })
    return () => { cancelled = true }
  }, [user?.id, reload])
  useEffect(() => {
    let cancelled = false
    setDocumentError("")
    if (!user || !Object.keys(courseIds).length) { setMaterials([]); setLoadingDocuments(false); return }
    setLoadingDocuments(true)
    Promise.allSettled(Object.entries(courseIds).map(async ([course, id]) => {
      const result = await listDocuments(id)
      return result.documents.map((document) => makeMaterial(document, course))
    })).then((results) => {
      if (cancelled) return
      const failures = results.filter((result) => result.status === "rejected")
      setMaterials(results.flatMap((result) => result.status === "fulfilled" ? result.value : []))
      if (failures.length) setDocumentError("일부 과목의 자료를 불러오지 못했어요. 다시 시도해 주세요.")
      setLoadingDocuments(false)
    })
    return () => { cancelled = true }
  }, [user?.id, courseIds, reload])
  const uploadPdf: PdfUploadHandler = async (file, course) => {
    const id = courseIds[course]
    if (!id || !user) throw new Error("먼저 과목을 연결해 주세요.")
    const userId = user.id
    await uploadDocument(file, id)
    if (activeUser.current === userId) setReload((value) => value + 1)
  }
  const openMaterial = (material: CourseMaterial, page?: number) => {
    const nextIds = rememberDocument(recentIds, material.documentId)
    setRecentIds(nextIds)
    if (user) { try { localStorage.setItem(`ieobom-recent-pdfs:${user.id}`, JSON.stringify(nextIds)) } catch { /* PDF navigation remains available when storage is full. */ } }
    setInitialPage(page); setSelectedCourse(material.course); setSelectedMaterial(material); setView("workspace")
  }
  const recentMaterials = recentIds.flatMap(id => {
    const material = materials.find(item => item.documentId === id)
    return material ? [material] : []
  })
  const openWorkspace = (course: string | null) => { setView("workspace"); setSelectedCourse(course); setSelectedMaterial(null); setReload(value => value + 1) }
  const openMap = () => { setView("map"); setSelectedCourse(null); setSelectedMaterial(null) }
  const removePdf = async (material: CourseMaterial) => {
    const userId = user?.id
    await deleteDocument(material.documentId)
    if (activeUser.current === userId) { setMaterials(items => items.filter(item => item.id !== material.id)); setReload(value => value + 1) }
  }
  if (checkingSession) return <main className="login-page"><p role="status">로그인을 확인하고 있어요.</p></main>
  if (!user) return <>{sessionError && <p className="session-error" role="alert">{sessionError}</p>}<LoginScreen onLogin={login} /></>
  return <AppShell user={user} view={view} recentMaterials={recentMaterials} onOpenRecent={openMaterial} onOpenSavedQuestions={() => { setView("saved"); setSelectedCourse(null); setSelectedMaterial(null) }} onOpenMap={() => { setView("map"); setSelectedCourse(null); setSelectedMaterial(null) }} selectedCourse={selectedCourse} selectedMaterial={selectedMaterial} onOpenWorkspace={openWorkspace} onLogout={() => { void apiLogout().catch(() => {}) }}>
    {view === "workspace" && documentError && <div className="document-load-error" role="alert"><p>{documentError}</p><button type="button" onClick={() => setReload((value) => value + 1)}>다시 시도</button></div>}
    {view === "map" && <CurriculumMap key={user.id} userId={user.id} onEnrollmentChanged={() => setReload(value => value + 1)} onOpenCourse={(id, name) => { const entry = Object.entries(courseIds).find(([, courseId]) => courseId === id); openWorkspace(entry?.[0] ?? name) }} />}
    {view === "saved" && <SavedQuestionsView materials={materials} onOpen={openMaterial} />}
    {view === "workspace" && !selectedCourse && <WorkspacePicker recentDocumentIds={recentIds} courseLoading={loadingCourses} courseError={courseError} courseProgress={courseProgress} courseStatuses={courseStatuses} onOpenMap={openMap} onRetry={() => setReload(value => value + 1)} courseIds={courseIds} materials={materials} loading={loadingDocuments || Boolean(documentError)} onSelect={openWorkspace} onOpenMaterial={openMaterial} />}
    {selectedCourse && !selectedMaterial && <>
      {loadingDocuments && !materials.some(material => material.course === selectedCourse) ? <div className="library-empty" role="status">강의자료를 불러오고 있어요.</div> : <WorkspaceLibrary key={selectedCourse} course={selectedCourse} materials={materials} onUpload={uploadPdf} onDelete={removePdf} onSelect={openMaterial} />}
    </>}
    {selectedMaterial && <UploadedPdfViewer key={`${selectedMaterial.id}:${initialPage ?? "resume"}`} material={selectedMaterial} initialPage={initialPage} onProgress={(id, progress) => setMaterials(items => items.map(item => item.documentId === id ? { ...item, readingProgress: progress } : item))} onChanged={() => setReload(value => value + 1)} />}
  </AppShell>
}
