const RECENT_LIMIT = 3

export function readRecentDocuments(value: string | null): string[] {
  try {
    const parsed: unknown = JSON.parse(value ?? '[]')
    if (!Array.isArray(parsed)) return []
    return [...new Set(parsed.filter((id): id is string => typeof id === 'string' && id.trim().length > 0))].slice(0, RECENT_LIMIT)
  } catch { return [] }
}

export function rememberDocument(ids: string[], documentId: string): string[] {
  return [documentId, ...ids.filter(id => id !== documentId)].slice(0, RECENT_LIMIT)
}
