"use client";
import { useEffect, useRef } from "react";
import { Box, CircularProgress, Typography } from "@mui/material";
import type { IChartApi } from "lightweight-charts";
import { formatPrice } from "@/lib/formatters";

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
  /** Compact mode for small/mobile/embedded charts: shorter labels, slimmer lines. */
  compact?: boolean;
}

const EMA_CONFIG = [
  { key: "ema20" as const,  color: "#6366f1", width: 1 },
  { key: "ema50" as const,  color: "#8b5cf6", width: 1 },
  { key: "ema100" as const, color: "#a78bfa", width: 1 },
  { key: "ema200" as const, color: "#c4b5fd", width: 2 },
];

// Labeled horizontal price lines drawn directly on the candlestick series.
// Entry is the most prominent (solid, thick, brand indigo); SL red; targets green.
const LEVEL_CONFIG = [
  { key: "entry" as const,     color: "#6366f1", dash: false, width: 3, label: "Entry" },
  { key: "stop_loss" as const, color: "#ef4444", dash: true,  width: 2, label: "SL"    },
  { key: "t1" as const,        color: "#4ade80", dash: true,  width: 1, label: "T1"     },
  { key: "t2" as const,        color: "#22c55e", dash: true,  width: 1, label: "T2"     },
  { key: "t3" as const,        color: "#16a34a", dash: true,  width: 1, label: "T3"     },
];

export function GATEChart({ bars, signal, height = 480, loading = false, compact = false }: GATEChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || !bars.length || loading) return;

    let chart: IChartApi;

    // Dynamic import to avoid SSR issues
    // lightweight-charts v5 uses chart.addSeries(SeriesType, options) instead of
    // chart.addCandlestickSeries() / chart.addLineSeries()
    import("lightweight-charts").then((lw) => {
      if (!containerRef.current) return;

      const { createChart, CandlestickSeries, LineSeries, ColorType, LineStyle } = lw as any;

      chart = createChart(containerRef.current, {
        autoSize: true,
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

      // Candlestick series (v5 API)
      const candles = chart.addSeries(CandlestickSeries, {
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

      // EMA overlays (v5 API)
      EMA_CONFIG.forEach(({ key, color, width }) => {
        const emaData = bars
          .filter((b) => b[key] != null)
          .map((b) => ({ time: b.time as unknown as string, value: b[key] as number }));
        if (!emaData.length) return;
        const s = chart.addSeries(LineSeries, {
          color,
          lineWidth: width as 1 | 2 | 3 | 4,
          priceLineVisible: false,
        });
        s.setData(emaData);
      });

      // Signal level horizontal lines with on-chart labels (v5 createPriceLine).
      // Titles render as visible labels on the line; axis label shows the price.
      const isCompact = compact || height < 300;
      if (signal) {
        LEVEL_CONFIG.forEach(({ key, color, dash, width, label }) => {
          const val = signal[key];
          if (val == null) return;
          candles.createPriceLine({
            price: val,
            color,
            lineWidth: (isCompact && width > 2 ? 2 : width) as 1 | 2 | 3 | 4,
            lineStyle: dash ? LineStyle.Dashed : LineStyle.Solid,
            axisLabelVisible: true,
            title: isCompact ? label : `${label} ${formatPrice(val)}`,
          });
        });
      }

      chart.timeScale().fitContent();
    });

    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [bars, signal, height, loading, compact]);

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
