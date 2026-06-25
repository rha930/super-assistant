export type ChartType = 'line' | 'bar' | 'pie'

export interface DataPoint {
  x: string | number
  y: number
}

export interface Series {
  name: string
  data: DataPoint[]
}

export interface GraphPayload {
  id: string
  title: string
  chartType: ChartType
  xLabel?: string
  yLabel?: string
  series: Series[]
  options?: {
    stacked?: boolean
    showLegend?: boolean
    [key: string]: unknown
  }
}

export interface GraphArtifact {
  type: 'graph'
  graph: GraphPayload
}

export interface Artifact {
  type: string
  [key: string]: unknown
}

export interface ValidatedGraph {
  isValid: boolean
  graph?: GraphPayload
  error?: string
}
