import type { SparkPoint } from "@/hooks/usePriceStream";

interface SparklineProps {
  points: SparkPoint[];
  ticker: string;
  width?: number;
  height?: number;
}

/**
 * Mini price trace accumulated from the SSE stream since page load. SVG rather
 * than canvas: a dozen of these render more cheaply as paths than as contexts,
 * and they stay inspectable in tests.
 */
export default function Sparkline({ points, ticker, width = 64, height = 20 }: SparklineProps) {
  const testId = `watchlist-sparkline-${ticker}`;

  if (points.length < 2) {
    return (
      <svg
        data-testid={testId}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${ticker} price trace, waiting for data`}
      >
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="var(--color-line)"
          strokeWidth={1}
          strokeDasharray="2 3"
        />
      </svg>
    );
  }

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const y = (value: number) => height - 1 - ((value - min) / span) * (height - 2);

  const line = values
    .map((value, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(2)},${y(value).toFixed(2)}`)
    .join(" ");
  const area = `${line} L${width},${height} L0,${height} Z`;
  const rising = values[values.length - 1] >= values[0];
  const stroke = rising ? "var(--color-up)" : "var(--color-down)";
  const gradientId = `spark-${ticker}-${rising ? "up" : "down"}`;

  return (
    <svg
      data-testid={testId}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={`${ticker} price trace since page load`}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.28" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path d={line} fill="none" stroke={stroke} strokeWidth={1.25} strokeLinejoin="round" />
    </svg>
  );
}
