const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
const sessionKey = 'ieobom-auth'
type Tokens = { access_token: string; refresh_token: string }
export type User = { id: string; email: string; role: string; created_at: string }
export type ReadingProgress = { viewed_pages: number; total_pages: number | null; progress_percent: number | null }
export type DocumentProgress = ReadingProgress & { document_id: string; last_page_number: number | null; last_viewed_at: string | null }
export type Document = { document_id: string; filename: string; status: string; created_at: string; reading_progress?: Omit<DocumentProgress, 'document_id'> }
export type DocumentStatus = {
  document_id: string; status: string; job_status: string | null
  stage?: string | null; completed_pages?: number | null; total_pages?: number | null; stage_progress_percent?: number | null
  attempt?: number; error_code?: string | null; error_message?: string | null; can_retry?: boolean; next_retry_at?: string | null
}

function tokens(): Tokens | null {
  try { return JSON.parse(sessionStorage.getItem(sessionKey) || 'null') } catch { return null }
}
export function clearSession() {
  sessionStorage.removeItem(sessionKey)
  window.dispatchEvent(new Event('ieobom-session-ended'))
}
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}
async function errorFor(response: Response) {
  const body = await response.json().catch(() => null)
  const detail = body?.detail
  return new ApiError(response.status, typeof detail === 'string' ? detail : Array.isArray(detail)
    ? detail.map((item: { msg: string }) => item.msg).join(', ')
    : `요청을 처리하지 못했어요. (${response.status})`)
}
let refreshing: Promise<void> | null = null
async function refresh() {
  if (!refreshing) {
    const previous = tokens()
    refreshing = (async () => {
      if (!previous) throw new ApiError(401, '다시 로그인해 주세요.')
      const response = await fetch(`${baseUrl}/auth/refresh`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: previous.refresh_token }),
      })
      // A logout or a new login must not be overwritten by an old refresh.
      if (tokens()?.refresh_token !== previous.refresh_token) throw new ApiError(401, '로그인이 변경되었어요.')
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) clearSession()
        throw await errorFor(response)
      }
      sessionStorage.setItem(sessionKey, JSON.stringify(await response.json()))
    })().finally(() => { refreshing = null })
  }
  return refreshing
}
async function request<T>(path: string, init: RequestInit = {}, authenticated = true, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  if (authenticated && tokens()) headers.set('Authorization', `Bearer ${tokens()!.access_token}`)
  let response: Response
  try { response = await fetch(`${baseUrl}${path}`, { ...init, headers }) }
  catch { throw new Error('서버에 연결하지 못했어요. 네트워크 상태를 확인해 주세요.') }
  if (authenticated && response.status === 401 && retry) {
    await refresh()
    return request<T>(path, init, true, false)
  }
  if (!response.ok) throw await errorFor(response)
  return response.status === 204 ? undefined as T : response.json()
}
export async function authenticate(mode: 'login' | 'signup', email: string, password: string) {
  const result = await request<Tokens>(`/auth/${mode}`, { method: 'POST', body: JSON.stringify({ email, password }) }, false)
  sessionStorage.setItem(sessionKey, JSON.stringify(result))
  return getMe()
}
export const hasSession = () => Boolean(tokens()?.refresh_token)
export const getMe = () => request<User>('/auth/me')
export async function logout() {
  const current = tokens()
  clearSession()
  if (current) await request<void>('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token: current.refresh_token }) }, false)
}
export const listDocuments = (courseId: string) => request<{ documents: Document[] }>(`/documents?course_id=${encodeURIComponent(courseId)}`)
export const getDocumentStatus = (id: string) => request<DocumentStatus>(`/documents/${encodeURIComponent(id)}/status`)
export const getFileUrl = (id: string) => request<{ file_url: string; expires_in: number }>(`/documents/${encodeURIComponent(id)}/file-url`)
export async function uploadDocument(file: File, courseId: string) {
  const upload = await request<{ document_id: string; upload_url: string }>('/documents/upload-url', {
    method: 'POST', body: JSON.stringify({ course_id: courseId, filename: file.name, content_type: 'application/pdf', size_bytes: file.size }),
  })
  const response = await fetch(upload.upload_url, { method: 'PUT', headers: { 'Content-Type': 'application/pdf' }, body: file })
  if (!response.ok) throw new Error(`PDF 저장에 실패했어요. (${response.status})`)
  await request(`/documents/${encodeURIComponent(upload.document_id)}/complete`, { method: 'POST' })
  return upload.document_id
}

export type EnrollmentStatus = 'not_enrolled' | 'in_progress' | 'completed'
export type Course = { id: string; name: string; course_code: string | null; curriculum_year: number | null; curriculum_id?: string | null }
export type EnrolledCourse = Course & { enrollment_status: EnrollmentStatus; reading_progress: ReadingProgress }
export type Curriculum = { id: string; institution: string; department: string; entry_year: number; is_demo: boolean }
export type CourseRelation = { id: string; source_course_id: string; target_course_id: string; relation_type: string; source: string }
export type CurriculumMapData = { curriculum: Curriculum; courses: EnrolledCourse[]; relations: CourseRelation[] }
export type PageNote = { document_id: string; page_number: number; content: string | null }
export type EvidenceBlock = { block_id: string; bbox: [number, number, number, number] }
export type Explanation = { headline: string; body: string; flow: string[] }
export type RelatedCourse = { course_id: string; name: string; reason: string; next_topic: string; relation: 'previous' | 'next' | 'related'; source: 'ai_recommendation'; enrollment_status: EnrollmentStatus | null }
export type ResearchTrend = { paper_id: string; title: string; summary: string; year: number | null; url: string; searched_at: string; source: 'semantic_scholar' | 'gemini' }
export type Question = { analysis?: PageLearningData['analysis']; id: string; document_id: string; page_number: number; question_type: string; content: string; recommended_reason: string; prerequisite: string; learning_order: string; first_activity: string; created_at: string; is_saved: boolean; explanation?: Explanation | null; evidence_block_ids?: string[]; evidence_blocks?: EvidenceBlock[]; related_courses?: RelatedCourse[]; trends?: ResearchTrend[] }
export type LearningQuestion = { id: string; type: string; question: string; why_recommended: string; explanation: Explanation; evidence_block_ids: string[]; prerequisites: string[]; learning_steps: string[]; first_activity: string; related_courses: RelatedCourse[]; trends: ResearchTrend[]; is_saved: boolean }
export type PageLearningData = {
  page_number: number; analysis: { summary: string; concepts: { name: string; evidence_block_ids: string[] }[]; coverage: string; question_eligible: boolean; exclusion_reason: string | null }
  questions: LearningQuestion[]; width_pt: number; height_pt: number; evidence_blocks: EvidenceBlock[]; research_status: 'disabled' | 'ready' | 'unavailable'
}
export type ChatExchange = { id: string; question: string; explanation: string; answer_status: 'answered' | 'conversation' | 'insufficient_evidence'; evidence_block_ids: string[]; created_at: string }
const curriculumQuery = (id?: string) => id ? `?curriculum_id=${encodeURIComponent(id)}` : ''
export const listCourses = (curriculumId?: string) => request<{ courses: Course[] }>(`/courses${curriculumQuery(curriculumId)}`)
export const listMyCourses = (curriculumId?: string) => request<{ courses: EnrolledCourse[] }>(`/courses/me${curriculumQuery(curriculumId)}`)
export const listCurricula = () => request<{ curricula: Curriculum[] }>('/curricula')
export const getCurriculumMap = (id: string) => request<CurriculumMapData>(`/curricula/${encodeURIComponent(id)}/map`)
export const setEnrollment = (id: string, status: Exclude<EnrollmentStatus, 'not_enrolled'>) => request<{ course_id: string; status: EnrollmentStatus }>(`/courses/${encodeURIComponent(id)}/enrollment`, { method: 'PUT', body: JSON.stringify({ status }) })
export const removeEnrollment = (id: string) => request<void>(`/courses/${encodeURIComponent(id)}/enrollment`, { method: 'DELETE' })
export const getReadingProgress = (id: string) => request<DocumentProgress>(`/documents/${encodeURIComponent(id)}/progress`)
export const recordPageView = (id: string, page: number) => request<DocumentProgress>(`/documents/${encodeURIComponent(id)}/progress`, { method: 'PUT', body: JSON.stringify({ page_number: page }) })
export const retryAnalysis = (id: string) => request<{ document_id: string; job_id: string; job_status: string }>(`/documents/${encodeURIComponent(id)}/retry`, { method: 'POST' })
export const deleteDocument = (id: string) => request<void>(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' })
const pagePath = (id: string, page: number) => `/documents/${encodeURIComponent(id)}/pages/${page}`
export const getPageNote = (id: string, page: number) => request<PageNote>(`${pagePath(id, page)}/note`)
export const savePageNote = (id: string, page: number, content: string) => request<PageNote>(`${pagePath(id, page)}/note`, { method: 'PUT', body: JSON.stringify({ content }) })
export const listPageQuestions = (id: string, page: number) => request<{ questions: Question[] }>(`${pagePath(id, page)}/questions`)
export const listDocumentQuestions = (id: string) => request<{ questions: Question[] }>(`/documents/${encodeURIComponent(id)}/questions`)
export const getPageLearning = (id: string, page: number) => request<PageLearningData>(`${pagePath(id, page)}/learning`)
export const getPageChat = (id: string, page: number, limit = 20) => request<{ document_id: string; page_number: number; exchanges: ChatExchange[] }>(`${pagePath(id, page)}/chat?limit=${limit}`)
export const askAboutPage = (id: string, page: number, question: string) => request<ChatExchange>(`${pagePath(id, page)}/ask`, { method: 'POST', body: JSON.stringify({ question: question.trim() }) })
export const listSavedQuestions = () => request<{ questions: Question[] }>('/questions')
export const setQuestionSaved = (id: string, saved: boolean) => request<void>(`/questions/${encodeURIComponent(id)}/save`, { method: saved ? 'PUT' : 'DELETE' })
