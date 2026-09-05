"use client";

import { useEffect, useRef } from "react";
import type { IChartApi, ISeriesApi, UTCTimestamp } from "lightweight-charts";

export interface ChartPoint {
  time: number;
  value: number;
}

interface LineChartProps {
  points: ChartPoint[];
  color: string;
  /** Right price scale visible? The sparkline-sized P&L chart hides it. */
  showPriceScale?: boolean;
  showTimeScale?: boolean;
  precision?: number;
  className?: string;
}

/** Strictly ascending integer-second series, as lightweight-charts requires. */
function toSeriesData(points: ChartPoint[]) {
  const byTime = new Map<number, number>();
  for (const p of points) {
    if (!Number.isFinite(p.time) || !Number.isFinite(p.value)) continue;
    byTime.set(Math.floor(p.time), p.value);
  }
  return [...byTime.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([time, value]) => ({ time: time as UTCTimestamp, value }));
}

/**
 * Canvas area chart (TradingView Lightweight Charts). The library is imported
 * lazily inside an effect so the static export never evaluates it in Node.
 */
export default function LineChart({
  points,
  color,
  showPriceScale = true,
  showTimeScale = true,
  precision = 2,
  className = "",
}: LineChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const pointsRef = useRef(points);
  pointsRef.current = points;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let chart: IChartApi | null = null;
    let observer: ResizeObserver | null = null;

    void (async () => {
      const { AreaSeries, createChart } = await import("lightweight-charts");
      if (disposed || !containerRef.current) return;

      chart = createChart(containerRef.current, {
        layout: {
          background: { color: "transparent" },
          textColor: "#8494a8",
          fontSize: 10,
          attributionLogo: false,
        },
        grid: {
          vertLines: { color: "rgba(34,44,58,0.45)" },
          horzLines: { color: "rgba(34,44,58,0.45)" },
        },
        rightPriceScale: { visible: showPriceScale, borderColor: "#222c3a" },
        timeScale: { visible: showTimeScale, borderColor: "#222c3a", timeVisible: true, secondsVisible: false },
        crosshair: {
          vertLine: { color: "#3a4757", labelBackgroundColor: "#1d2735" },
          horzLine: { color: "#3a4757", labelBackgroundColor: "#1d2735" },
        },
        handleScale: false,
        handleScroll: false,
        autoSize: false,
        width: containerRef.current.clientWidth || 320,
        height: containerRef.current.clientHeight || 160,
      });

      const series = chart.addSeries(AreaSeries, {
        lineColor: color,
        lineWidth: 2,
        topColor: `${color}55`,
        bottomColor: `${color}05`,
        priceLineVisible: false,
        lastValueVisible: showPriceScale,
        priceFormat: { type: "price", precision, minMove: 1 / 10 ** precision },
      });
      series.setData(toSeriesData(pointsRef.current));
      chart.timeScale().fitContent();

      chartRef.current = chart;
      seriesRef.current = series;

      observer = new ResizeObserver((entries) => {
        const box = entries[0]?.contentRect;
        if (!box || !chart) return;
        chart.resize(Math.max(box.width, 1), Math.max(box.height, 1));
      });
      observer.observe(containerRef.current);
    })();

    return () => {
      disposed = true;
      observer?.disconnect();
      chartRef.current = null;
      seriesRef.current = null;
      chart?.remove();
    };
    // Colour and scale options are set once at creation; data flows through the
    // effect below. Recreating the chart on every prop tick would flicker.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    seriesRef.current?.setData(toSeriesData(points));
  }, [points]);

  useEffect(() => {
    seriesRef.current?.applyOptions({
      lineColor: color,
      topColor: `${color}55`,
      bottomColor: `${color}05`,
    });
  }, [color]);

  return <div ref={containerRef} className={`h-full w-full ${className}`} />;
}
