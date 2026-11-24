export type CourseConnections = Record<string, string>

export function isCourseId(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
}

export function readCourseConnections(raw: string | null): CourseConnections {
  try {
    const value: unknown = JSON.parse(raw || '{}')
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
    return Object.fromEntries(Object.entries(value).filter(([name, id]) =>
      name.trim().length > 0 && typeof id === 'string' && isCourseId(id),
    ))
  } catch { return {} }
}
