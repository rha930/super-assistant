import type { GraphPayload, ValidatedGraph, ChartType } from '../types/graph'

const SUPPORTED_CHART_TYPES: ChartType[] = ['line', 'bar', 'pie']
const MAX_PAYLOAD_SIZE = 1024 * 100 // 100 KB

export function isValidChartType(type: unknown): type is ChartType {
  return typeof type === 'string' && SUPPORTED_CHART_TYPES.includes(type as ChartType)
}

export function validateDataPoint(point: unknown): boolean {
  if (!point || typeof point !== 'object') return false
  const p = point as Record<string, unknown>
  return (
    (typeof p.x === 'string' || typeof p.x === 'number') &&
    typeof p.y === 'number' &&
    !isNaN(p.y)
  )
}

export function validateSeries(series: unknown): boolean {
  if (!Array.isArray(series)) return false
  if (series.length === 0) return false

  return series.every((s) => {
    if (!s || typeof s !== 'object') return false
    const ser = s as Record<string, unknown>
    return (
      typeof ser.name === 'string' &&
      Array.isArray(ser.data) &&
      ser.data.length > 0 &&
      ser.data.every(validateDataPoint)
    )
  })
}

export function validateGraphPayload(payload: unknown): ValidatedGraph {
  if (!payload || typeof payload !== 'object') {
    return { isValid: false, error: 'Graph payload must be an object' }
  }

  const p = payload as Record<string, unknown>

  // Validate id
  if (typeof p.id !== 'string' || p.id.trim().length === 0) {
    return { isValid: false, error: 'Graph id must be a non-empty string' }
  }

  // Validate title
  if (typeof p.title !== 'string' || p.title.trim().length === 0) {
    return { isValid: false, error: 'Graph title must be a non-empty string' }
  }

  // Validate chartType
  if (!isValidChartType(p.chartType)) {
    return { isValid: false, error: `Chart type must be one of: ${SUPPORTED_CHART_TYPES.join(', ')}` }
  }

  // Validate series
  if (!validateSeries(p.series)) {
    return { isValid: false, error: 'Series must be a non-empty array with valid data points' }
  }

  // Optional labels
  if (p.xLabel !== undefined && typeof p.xLabel !== 'string') {
    return { isValid: false, error: 'xLabel must be a string' }
  }

  if (p.yLabel !== undefined && typeof p.yLabel !== 'string') {
    return { isValid: false, error: 'yLabel must be a string' }
  }

  const graphPayload: GraphPayload = {
    id: p.id as string,
    title: p.title as string,
    chartType: p.chartType as ChartType,
    xLabel: (p.xLabel as string) || undefined,
    yLabel: (p.yLabel as string) || undefined,
    series: p.series as any[],
    options: (p.options as Record<string, unknown>) || {}
  }

  return { isValid: true, graph: graphPayload }
}

export function extractGraphArtifacts(artifacts?: unknown[]): GraphPayload[] {
  if (!Array.isArray(artifacts)) return []

  return artifacts
    .filter((a) => {
      if (!a || typeof a !== 'object') return false
      return (a as Record<string, unknown>).type === 'graph'
    })
    .map((a) => {
      const artifact = a as Record<string, unknown>
      const validation = validateGraphPayload(artifact.graph)
      return validation.isValid ? validation.graph! : null
    })
    .filter((g) => g !== null) as GraphPayload[]
}
