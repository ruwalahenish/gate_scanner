"use client";
import { useEffect, useRef } from "react";
import { Box, CircularProgress, Typography } from "@mui/material";
import type {
  IChartApi, ISeriesApi, CandlestickData, LineData,
} from "lightweight-charts";

interface Bar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  ema20?: number | null;
  ema50?: number | null;
  ema100?: number | null;
  ema200?: number | null;
}

interface SignalLevels {
  entry?: number | null;
  stop_loss?: number | null;
  t1?: number | null;
  t2?: number | null;
  t3?: number | null;
}

interface GATEChartProps {
  bars: Bar[];
  signal?: SignalLevels | null;
  height?: number;
  loading?: boolean;
}

const EMA_CONFIG = [
  { key: "ema20" as const,  color: "#6366f1", width: 1 },
  { key: "ema50" as const,  color: "#8b5cf6", width: 1 },
  { key: "ema100" as const, color: "#a78bfa", width: 1 },
  { key: "ema200" as const, color: "#c4b5fd", width: 2 },
];

const LEVEL_CONFIG = [
  { key: "t3" as const,        color: "#16a34a", dash: true  },
  { key: "t2" as const,        color: "#22c55e", dash: true  },
  { key: "t1" as const,        color: "#4ade80", dash: true  },
  { key: "entry" as const,     color: "#6366f1", dash: false },
  { key: "stop_loss" as const, color: "#ef4444", dash: true  },
];

export function GATEChart({ bars, signal, height = 480, loading = false }: GATEChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || !bars.length || loading) return;

    let chart: IChartApi;

    // Dynamic import to avoid SSR issues
    import("lightweight-charts").then(({ createChart, ColorType, LineStyle }) => {
      if (!containerRef.current) return;

      chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height,
        layout: {
          background: { type: ColorType.Solid, color: "#1a1a24" },
          textColor: "#94a3b8",
        },
        grid: {
          vertLines: { color: "#1e293b" },
          horzLines: { color: "#1e293b" },
        },
        crosshair: { mode: 1 },
        rightPriceScale: { borderColor: "#1e293b" },
        timeScale: {
          borderColor: "#1e293b",
          timeVisible: true,
          secondsVisible: false,
        },
      });

      chartRef.current = chart;

      // Candlestick series
      const candles = chart.addCandlestickSeries({
        upColor: "#22c55e",
        downColor: "#ef4444",
        borderUpColor: "#22c55e",
        borderDownColor: "#ef4444",
        wickUpColor: "#22c55e",
        wickDownColor: "#ef4444",
      });
      candles.setData(
        bars.map((b) => ({
          time: b.time as unknown as string,
          open: b.open,
          high: b.high,
          low: b.low,
          close: b.close,
        }))
      );

      // EMA overlays
      EMA_CONFIG.forEach(({ key, color, width }) => {
        const emaData = bars
          .filter((b) => b[key] != null)
          .map((b) => ({ time: b.time as unknown as string, value: b[key] as number }));
        if (!emaData.length) return;
        const s = chart.addLineSeries({ color, lineWidth: width as 1 | 2 | 3 | 4, priceLineVisible: false });
        s.setData(emaData);
      });

      // Signal level horizontal lines
      if (signal && bars.length) {
        const firstTime = bars[0].time as unknown as string;
        const lastTime = bars[bars.length - 1].time as unknown as string;

        LEVEL_CONFIG.forEach(({ key, color, dash }) => {
          const val = signal[key];
          if (!val) return;
          const s = chart.addLineSeries({
            color,
            lineWidth: 1,
            lineStyle: dash ? LineStyle.Dashed : LineStyle.Solid,
            priceLineVisible: false,
            lastValueVisible: true,
          });
          s.setData([
            { time: firstTime, value: val },
            { time: lastTime, value: val },
          ]);
        });
      }

      chart.timeScale().fitContent();

      // Responsive resize
      const ro = new ResizeObserver(() => {
        if (containerRef.current && chartRef.current) {
          chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
        }
      });
      ro.observe(containerRef.current);

      return () => ro.disconnect();
    });

    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [bars, signal, height, loading]);

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!bars.length) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height }}>
        <Typography color="text.secondary">No chart data available</Typography>
      </Box>
    );
  }

  return <div ref={containerRef} style={{ width: "100%", height }} />;
}
