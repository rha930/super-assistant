<template>
  <div class="w-full h-full flex flex-col">
    <div v-if="renderError" class="text-sm text-red-600 dark:text-red-400 p-2">
      {{ renderError }}
    </div>
    <div ref="chartContainer" class="flex-1 relative min-h-0"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import { Chart as ChartJS, registerables } from 'chart.js'
import type { GraphPayload, ChartType } from '../types/graph'

ChartJS.register(...registerables)

interface Props {
  graph: GraphPayload
}

const props = defineProps<Props>()

const chartContainer = ref<HTMLDivElement>()
const renderError = ref<string>('')
let chartInstance: ChartJS<any> | null = null
let resizeObserver: ResizeObserver | null = null

const prepareChartData = (graph: GraphPayload) => {
  const datasets = graph.series.map((series, idx) => {
    const colors = getColorForIndex(idx)
    return {
      label: series.name,
      data: series.data.map((point) => ({
        x: point.x,
        y: point.y
      })),
      borderColor: colors.border,
      backgroundColor: colors.background,
      fill: graph.chartType === 'line' && graph.options?.stacked !== false,
      tension: 0.4,
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: colors.border,
      pointBorderColor: 'white',
      pointBorderWidth: 2
    }
  })

  return {
    labels: graph.series[0]?.data.map((p) => String(p.x)) || [],
    datasets
  }
}

const getColorForIndex = (idx: number) => {
  const colors = [
    {
      border: '#3b82f6',
      background: 'rgba(59, 130, 246, 0.1)'
    },
    {
      border: '#ef4444',
      background: 'rgba(239, 68, 68, 0.1)'
    },
    {
      border: '#10b981',
      background: 'rgba(16, 185, 129, 0.1)'
    },
    {
      border: '#f59e0b',
      background: 'rgba(245, 158, 11, 0.1)'
    },
    {
      border: '#8b5cf6',
      background: 'rgba(139, 92, 246, 0.1)'
    }
  ]
  return colors[idx % colors.length]
}

const getChartType = (graphType: ChartType) => {
  switch (graphType) {
    case 'bar':
      return 'bar'
    case 'pie':
      return 'doughnut'
    case 'line':
    default:
      return 'line'
  }
}

const renderChart = async () => {
  await nextTick()

  if (!chartContainer.value) {
    renderError.value = 'Chart container not found'
    return
  }

  try {
    renderError.value = ''

    // Destroy existing chart if any
    if (chartInstance) {
      chartInstance.destroy()
      chartInstance = null
    }

    const canvas = document.createElement('canvas')
    chartContainer.value.innerHTML = ''
    chartContainer.value.appendChild(canvas)

    const data = prepareChartData(props.graph)
    const isDarkMode = document.documentElement.classList.contains('theme-dark')
    const textColor = isDarkMode ? '#e5e7eb' : '#111827'
    const gridColor = isDarkMode ? '#374151' : '#e5e7eb'

    chartInstance = new ChartJS(canvas, {
      type: getChartType(props.graph.chartType),
      data,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: props.graph.options?.showLegend !== false,
            labels: {
              color: textColor,
              font: {
                size: 12
              }
            }
          },
          title: {
            display: false
          }
        },
        scales: {
          x: {
            type: props.graph.chartType === 'pie' ? undefined : 'category',
            ticks: {
              color: textColor
            },
            grid: {
              color: gridColor
            }
          },
          y: {
            display: props.graph.chartType !== 'pie',
            ticks: {
              color: textColor
            },
            grid: {
              color: gridColor
            }
          }
        }
      }
    })

    if (resizeObserver && chartContainer.value) {
      resizeObserver.observe(chartContainer.value)
    }
  } catch (error) {
    console.error('Failed to render chart:', error)
    renderError.value = `Failed to render chart: ${error instanceof Error ? error.message : 'unknown error'}`
  }
}

onMounted(() => {
  resizeObserver = new ResizeObserver(() => {
    if (chartInstance) {
      chartInstance.resize()
    }
  })
  renderChart()
})

watch(() => props.graph, renderChart, { deep: true })
</script>

<style scoped>
/* Ensure chart container fills parent */
div {
  width: 100%;
}
</style>
