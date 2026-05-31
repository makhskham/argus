"use client"
import { useEffect, useRef } from "react"
import { createChart, ColorType, LineSeries, Time } from "lightweight-charts"

interface PriceChartProps {
  ticker: string
}

export function PriceChart({ ticker }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#050505" }, textColor: "#4b5563" },
      grid: { vertLines: { color: "#0d0d0d" }, horzLines: { color: "#0d0d0d" } },
      crosshair: { vertLine: { color: "#2a2a2a" }, horzLine: { color: "#2a2a2a" } },
      rightPriceScale: { borderColor: "#161616" },
      timeScale: { borderColor: "#161616" },
      width: containerRef.current.clientWidth,
      height: 200,
    })
    const lineSeries = chart.addSeries(LineSeries, {
      color: "#22c55e",
      lineWidth: 1,
      lastValueVisible: true,
      priceLineVisible: false,
    })
    const now = Math.floor(Date.now() / 1000)
    const day = 86400
    lineSeries.setData(
      Array.from({ length: 30 }, (_, i) => ({
        time: (now - (29 - i) * day) as unknown as Time,
        value: 100 + Math.sin(i * 0.4) * 10 + i * 0.5,
      }))
    )
    chart.timeScale().fitContent()
    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    })
    ro.observe(containerRef.current)
    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [ticker])

  return <div ref={containerRef} className="w-full" />
}
