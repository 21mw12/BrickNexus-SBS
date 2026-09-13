export interface HeatmapDisplayBuckets {
  startTimes: string[]
  endTimes: string[]
  values: Array<Array<number | null>>
  normalizedValues: Array<Array<number | null>>
}

function normalize(values: Array<number | null>) {
  const numeric = values.filter((value): value is number => value != null)
  if (!numeric.length) return values.map(() => null)
  const minimum = Math.min(...numeric)
  const maximum = Math.max(...numeric)
  if (minimum === maximum) return values.map(value => value == null ? null : 50)
  return values.map(value => value == null ? null : (value - minimum) / (maximum - minimum) * 100)
}

/**
 * 将高精度计算桶合并为可辨识的热力图显示桶。
 * 只聚合桶内已有值，不跨空白区间插值，因此长时间缺失仍然可见。
 */
export function buildHeatmapDisplayBuckets(
  times: string[],
  valuesByPoint: Array<Array<number | null>>,
  actualEndTime: string,
  maxColumns = 160,
): HeatmapDisplayBuckets {
  if (!times.length) return { startTimes: [], endTimes: [], values: valuesByPoint.map(() => []), normalizedValues: valuesByPoint.map(() => []) }

  const largestObservedCount = Math.max(0, ...valuesByPoint.map(values => values.filter(value => value != null).length))
  const usefulColumns = largestObservedCount ? Math.ceil(largestObservedCount * 0.75) : 24
  const columnCount = Math.min(times.length, Math.max(12, Math.min(maxColumns, usefulColumns)))
  const ranges = Array.from({ length: columnCount }, (_, column) => ({
    start: Math.floor(column * times.length / columnCount),
    end: Math.floor((column + 1) * times.length / columnCount),
  }))
  const values = valuesByPoint.map(pointValues => ranges.map(({ start, end }) => {
    const numeric = pointValues.slice(start, end).filter((value): value is number => value != null && Number.isFinite(value))
    return numeric.length ? numeric.reduce((sum, value) => sum + value, 0) / numeric.length : null
  }))

  return {
    startTimes: ranges.map(range => times[range.start]!),
    endTimes: ranges.map((range, index) => index + 1 < ranges.length ? times[ranges[index + 1]!.start]! : actualEndTime),
    values,
    normalizedValues: values.map(normalize),
  }
}
