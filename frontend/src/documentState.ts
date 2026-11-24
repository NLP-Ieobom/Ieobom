import type { DocumentStatus } from './api'
export function documentState(value: Pick<DocumentStatus, 'status' | 'job_status' | 'stage'>) {
  const document = value.status.toLowerCase()
  const job = value.job_status?.toLowerCase()
  if ([document, job].some(status => status && /^(failed|error|cancelled|canceled)$/.test(status))) return { label: '분석 실패', terminal: true }
  if (value.stage === 'analysis_skipped') return { label: '질문 분석 생략', terminal: true }
  if ([document, job].some(status => status && /^(ready|completed|complete|processed|succeeded)$/.test(status))) return { label: '분석 완료', terminal: true }
  const stages: Record<string, string> = { uploading: '업로드 중', queued: '분석 대기', downloading: 'PDF 준비 중', extracting: '내용 추출 중', analyzing: '질문 생성 중' }
  if (value.stage && stages[value.stage]) return { label: stages[value.stage], terminal: false }
  return { label: /^(uploaded|uploading)$/.test(document) && !job ? '업로드 완료' : '분석 중', terminal: false }
}
