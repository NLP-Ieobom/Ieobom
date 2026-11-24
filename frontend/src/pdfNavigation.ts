export function keyboardPdfPage(event: { key: string; altKey?: boolean; ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean; defaultPrevented?: boolean }, current: number, total: number, editing: boolean) {
  if (editing || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || !total) return null
  if (event.key === 'ArrowRight') return Math.min(total, current + 1)
  if (event.key === 'ArrowLeft') return Math.max(1, current - 1)
  return null
}
