export type GapDisplayMode = 'auto' | 'strict' | 'connect'
export type TimeAxisValue = string | number
export type TimeSeriesChartPoint = [TimeAxisValue, number | null]

function median(values: number[]) {
  const ordered = [...values].sort((left, right) => left - right)
  const middle = Math.floor(ordered.length / 2)
  return ordered.length % 2 ? ordered[middle]! : (ordered[middle - 1]! + ordered[middle]!) / 2
}

/**
 * Builds display data without manufacturing measurement values.
 *
 * In automatic mode, the median distance between populated buckets represents
 * the point's normal acquisition cadence. Short empty runs are omitted so the
 * neighboring measurements remain connected; a null marker is retained when
 * the distance exceeds three normal cadence intervals.
 */
export function buildGapAwareData(
  times: TimeAxisValue[],
  values: Array<number | null>,
  mode: GapDisplayMode = 'auto',
): TimeSeriesChartPoint[] {
  const all = times.map((time, index) => [time, values[index] ?? null] as TimeSeriesChartPoint)
  if (mode === 'strict') return all

  const populated = values.flatMap((value, index) => value == null || index >= times.length ? [] : [index])
  if (mode === 'connect') return populated.map(index => [times[index]!, values[index] as number])
  if (populated.length < 3) return all

  const steps = populated.slice(1).map((index, position) => index - populated[position]!)
  const typicalStep = Math.max(1, median(steps))
  const breakThreshold = Math.max(3, typicalStep * 3)
  const result: TimeSeriesChartPoint[] = []

  populated.forEach((index, position) => {
    if (position > 0) {
      const previous = populated[position - 1]!
      if (index - previous > breakThreshold) {
        const missingIndex = Math.min(previous + 1, times.length - 1)
        result.push([times[missingIndex]!, null])
      }
    }
    result.push([times[index]!, values[index] as number])
  })
  return result
}
