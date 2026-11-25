import { useEffect, useMemo, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy, type PDFPageProxy } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import questionMarkerUrl from './assets/question-marker.png'
import { evidenceFor } from './learningData'
import type { Question } from './api'
GlobalWorkerOptions.workerSrc = workerUrl

function PdfPage({ page, scale, questions, onQuestionClick, onRendered }: { page: PDFPageProxy; scale: number; questions: Question[]; onQuestionClick?: (question: Question) => void; onRendered: (page: number) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [error, setError] = useState('')
  const rendered = useRef(onRendered)
  rendered.current = onRendered
  const viewport = page.getViewport({ scale })
  useEffect(() => {
    const target = canvas.current
    if (!target) return
    const viewport = page.getViewport({ scale })
    const density = Math.min(window.devicePixelRatio || 1, 2)
    target.width = Math.floor(viewport.width * density)
    target.height = Math.floor(viewport.height * density)
    const context = target.getContext('2d')
    if (!context) return
    let cancelled = false
    setError('')
    const task = page.render({ canvas: target, canvasContext: context, viewport, transform: [density, 0, 0, density, 0, 0] })
    task.promise.then(() => { if (!cancelled) rendered.current(page.pageNumber) })
      .catch(reason => { if (!cancelled && reason?.name !== 'RenderingCancelledException') setError('페이지를 표시하지 못했어요.') })
    return () => { cancelled = true; task.cancel() }
  }, [page, scale])
  const markers = useMemo(() => {
    const spacing = 36
    const maxLeft = Math.max(4, viewport.width - spacing)
    const maxTop = Math.max(4, viewport.height - spacing)
    const placed: { question: Question; left: number; top: number }[] = []
    for (const question of questions) {
      const [block] = evidenceFor(question.evidence_blocks ?? [], question.evidence_block_ids ?? [])
      const left = block ? Math.max(4, Math.min(maxLeft, block.bbox[2] * viewport.width + 12)) : maxLeft
      const preferredTop = block ? Math.max(4, Math.min(maxTop, (block.bbox[1] + block.bbox[3]) / 2 * viewport.height - 16)) : 4
      const neighbors = placed.filter(marker => Math.abs(marker.left - left) < spacing)
      const candidates = [preferredTop, ...neighbors.flatMap(marker => [marker.top + spacing, marker.top - spacing])]
      candidates.sort((a, b) => Math.abs(a - preferredTop) - Math.abs(b - preferredTop))
      const top = candidates.find(candidate => candidate >= 4 && candidate <= maxTop
        && neighbors.every(marker => Math.abs(marker.top - candidate) >= spacing)) ?? preferredTop
      placed.push({ question, left, top })
    }
    return placed
  }, [questions, viewport.width, viewport.height])
  return <div className="pdf-sheet" data-pdf-page={page.pageNumber} style={{ width: viewport.width, height: viewport.height }}>
    <canvas key={`${page.pageNumber}:${scale}`} ref={canvas} aria-label={`${page.pageNumber}페이지`} style={{ width: '100%', height: '100%' }} />
    {markers.map(({ question, left, top }) => (
      <button key={question.id} type="button" className="pdf-question-marker" aria-label={`발견 질문: ${question.content}`} title={question.content} onClick={() => onQuestionClick?.(question)} style={{ left, top }}><img src={questionMarkerUrl} alt="" draggable={false} /></button>
    ))}
    {error && <p role="alert">{error}</p>}
  </div>
}

export default function PdfReader({ url, zoom, navigation, onPageChange, onPageCount, questions = [], onQuestionClick }: {
  url: string; zoom: number; navigation: { page: number; sequence: number }; onPageChange: (page: number) => void; onPageCount: (count: number) => void
  questions?: Question[]; onQuestionClick?: (question: Question) => void
}) {
  const root = useRef<HTMLDivElement>(null)
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null)
  const [page, setPage] = useState<PDFPageProxy | null>(null)
  const [width, setWidth] = useState(600)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const callbacks = useRef({ onPageChange, onPageCount })
  callbacks.current = { onPageChange, onPageCount }
  useEffect(() => {
    const element = root.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => { if (entry.contentRect.width > 0) setWidth(Math.max(100, entry.contentRect.width - 50)) })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  useEffect(() => {
    let cancelled = false
    setDocument(null); setPage(null); setError('')
    const source = new URL(url, window.location.href)
    const documentUrl = source.hostname === 'ieobom-materials.s3.amazonaws.com' ? `/pdf-file${source.pathname}${source.search}` : url
    const loading = getDocument({ url: documentUrl })
    loading.promise.then(pdf => {
      if (cancelled) return
      setDocument(pdf); callbacks.current.onPageCount(pdf.numPages)
    }).catch(() => { if (!cancelled) setError('PDF를 불러오지 못했어요. 다시 시도하거나 새 창에서 열어 주세요.') })
    return () => { cancelled = true; void loading.destroy() }
  }, [url, attempt])
  useEffect(() => {
    if (!document) return
    let cancelled = false
    setPage(null); setError('')
    const number = Math.max(1, Math.min(document.numPages, navigation.page))
    document.getPage(number).then(page => {
      if (cancelled) return
      setPage(page)
      if (root.current) { root.current.scrollTop = 0; root.current.scrollLeft = 0 }
    }).catch(() => { if (!cancelled) setError('페이지를 불러오지 못했어요.') })
    return () => { cancelled = true }
  }, [document, navigation])
  const pageQuestions = useMemo(() => questions.filter(question => question.page_number === page?.pageNumber), [questions, page?.pageNumber])
  const scale = page ? width / page.getViewport({ scale: 1 }).width * zoom / 100 : 1
  return <div className="pdf-reader" ref={root} tabIndex={0} aria-label="PDF 페이지" aria-keyshortcuts="ArrowLeft ArrowRight">
    {error ? <p role="alert">{error}<button onClick={() => setAttempt(value => value + 1)}>다시 시도</button></p> : !page && <p role="status">PDF를 불러오고 있어요.</p>}
    {page && <PdfPage key={page.pageNumber} page={page} scale={scale} questions={pageQuestions} onQuestionClick={onQuestionClick} onRendered={number => callbacks.current.onPageChange(number)} />}
  </div>
}
