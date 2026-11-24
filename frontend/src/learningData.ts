import type { EvidenceBlock, PageLearningData, Question } from './api'

export const questionLabels: Record<string, string> = {
  connect_prior: '이전 내용과 연결하기', understand_flow: '전체 흐름에서 이해하기',
  challenge: '당연한 내용 의심하기', apply: '실제 상황에 적용하기', extend: '강의 밖으로 확장하기',
}

export function learningQuestions(documentId: string, learning: PageLearningData): Question[] {
  return learning.questions.map(question => ({
    id: question.id, document_id: documentId, page_number: learning.page_number,
    question_type: question.type, content: question.question, recommended_reason: question.why_recommended,
    prerequisite: question.prerequisites.join('\n'), learning_order: question.learning_steps.join('\n'),
    first_activity: question.first_activity, created_at: '', is_saved: question.is_saved,
    analysis: learning.analysis, explanation: question.explanation, evidence_block_ids: question.evidence_block_ids,
    evidence_blocks: learning.evidence_blocks.filter(block => question.evidence_block_ids.includes(block.block_id)),
    related_courses: question.related_courses, trends: question.trends,
  }))
}

export function evidenceFor(blocks: EvidenceBlock[], ids: string[]): EvidenceBlock[] {
  return blocks.filter(block => ids.includes(block.block_id) && block.bbox.length === 4 && block.bbox.every(Number.isFinite)
    && block.bbox[0] >= 0 && block.bbox[1] >= 0 && block.bbox[2] <= 1 && block.bbox[3] <= 1
    && block.bbox[2] > block.bbox[0] && block.bbox[3] > block.bbox[1])
}

export function safeExternalUrl(value: string): string | undefined {
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : undefined } catch { return undefined }
}
