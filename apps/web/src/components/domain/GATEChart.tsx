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
  breakout_level?: number | null;
}

interface GATEChartProps {
  bars: Bar[];
  signal?: SignalLevels | null;
  height?: number;
  loading?: boolean;
  compact?: boolean;
}

// ── EMA overlays ─────────────────────────────────────────────────────────────
const EMA_CONFIG = [
  { key: "ema20"  as const, color: "#6366f1", width: 1 },
  { key: "ema50"  as const, color: "#8b5cf6", width: 1 },
  { key: "ema100" as const, color: "#a78bfa", width: 1 },
  { key: "ema200" as const, color: "#c4b5fd", width: 2 },
];

// ── Signal price lines (near current price — always within the candle range) ─
const PRICE_LINE_CONFIG = [
  { key: "breakout_level" as const, color: "#eab308", dash: false, width: 2, label: "Breakout" },
  { key: "entry"          as const, color: "#6366f1", dash: false, width: 3, label: "Entry"    },
  { key: "stop_loss"      as const, color: "#ef4444", dash: false, width: 2, label: "SL"       },
];

// ── Fibonacci extension targets (signal-conditional, LineSeries for autoscale) ─
const FIB_EXT_CONFIG = [
  { key: "t1" as const, color: "#4ade80", width: 3, label: "T1", ratio: "1.272×" },
  { key: "t2" as const, color: "#facc15", width: 3, label: "T2", ratio: "1.618×" },
  { key: "t3" as const, color: "#f97316", width: 3, label: "T3", ratio: "2.618×" },
];

// ── Standard Fibonacci retracement levels (always visible, every status) ─────
// Drawn from the auto-detected swing high → swing low of the visible bar range.
const FIB_RETR_LEVELS = [
  { ratio: 0.000, label: "0%",    color: "#64748b" },
  { ratio: 0.236, label: "23.6%", color: "#fbbf24" },
  { ratio: 0.382, label: "38.2%", color: "#fb923c" },
  { ratio: 0.500, label: "50%",   color: "#f87171" },
  { ratio: 0.618, label: "61.8%", color: "#c084fc" },
  { ratio: 0.786, label: "78.6%", color: "#818cf8" },
  { ratio: 1.000, label: "100%",  color: "#64748b" },
];

/**
 * Auto-detect the most recent significant swing high and the subsequent low
 * from the bar data so Fibonacci retracement lines can be computed without
 * needing a backend signal.
 *
 * Strategy:
 *   1. Take the last 150 bars (or fewer if less data available).
 *   2. Swing high = the bar with the highest `high` in that window.
 *   3. Swing low  = the bar with the lowest `low` AFTER the swing-high bar.
 *   4. Require at least an 8% range (high − low) / high to filter noise.
 */
function detectFibSwing(bars: Bar[]): { high: number; low: number } | null {
  if (bars.length < 20) return null;
  const lb = bars.slice(-150);

  let swingHigh = 0;
  let swingHighIdx = 0;
  lb.forEach((b, i) => {
    if (b.high > swingHigh) { swingHigh = b.high; swingHighIdx = i; }
  });

  let swingLow = Infinity;
  for (let i = swingHighIdx; i < lb.length; i++) {
    if (lb[i].low < swingLow) swingLow = lb[i].low;
  }

  if (!isFinite(swingLow) || swingLow >= swingHigh) return null;
  if ((swingHigh - swingLow) / swingHigh < 0.08) return null; // < 8% swing → skip

  return { high: swingHigh, low: swingLow };
}

export function GATEChart({
  bars,
  signal,
  height = 480,
  loading = false,
  compact = false,
}: GATEChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || !bars.length || loading) return;

    let chart: IChartApi;

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

      // ── Candlestick series ──────────────────────────────────────────────────
      const candles = chart.addSeries(CandlestickSeries, {
        upColor:         "#22c55e",
        downColor:       "#ef4444",
        borderUpColor:   "#22c55e",
        borderDownColor: "#ef4444",
        wickUpColor:     "#22c55e",
        wickDownColor:   "#ef4444",
      });
      candles.setData(
        bars.map((b) => ({
          time:  b.time as unknown as string,
          open:  b.open,
          high:  b.high,
          low:   b.low,
          close: b.close,
        }))
      );

      // ── EMA overlays ────────────────────────────────────────────────────────
      EMA_CONFIG.forEach(({ key, color, width }) => {
        const data = bars
          .filter((b) => b[key] != null)
          .map((b) => ({ time: b.time as unknown as string, value: b[key] as number }));
        if (!data.length) return;
        const s = chart.addSeries(LineSeries, {
          color,
          lineWidth:        width as 1 | 2 | 3 | 4,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        s.setData(data);
      });

      const firstTime = bars[0].time as unknown as string;
      const lastTime  = bars[bars.length - 1].time as unknown as string;
      const isCompact = compact || height < 300;

      // ── Fibonacci retracement (always drawn, every status) ─────────────────
      // Computed from the auto-detected swing high → swing low so the levels
      // are visible even when the stock is in WATCH, NO_ACTION, or no signal.
      const swing = detectFibSwing(bars);
      if (swing) {
        const range = swing.high - swing.low;
        FIB_RETR_LEVELS.forEach(({ ratio, label, color }) => {
          const price = swing.high - ratio * range;
          const s = chart.addSeries(LineSeries, {
            color,
            lineWidth:        1 as const,
            lineStyle:        LineStyle.Dashed,
            priceLineVisible: false,
            lastValueVisible: true,
            title: isCompact ? `Fib ${label}` : `Fib ${label}  ${formatPrice(price)}`,
          });
          s.setData([
            { time: firstTime, value: price },
            { time: lastTime,  value: price },
          ]);
        });
      }

      // ── Signal levels (only when a signal exists) ──────────────────────────
      if (signal) {
        // Entry / SL / Breakout Level as price lines (always within candle range)
        PRICE_LINE_CONFIG.forEach(({ key, color, dash, width, label }) => {
          const val = signal[key];
          if (val == null) return;
          candles.createPriceLine({
            price:            val,
            color,
            lineWidth:        (isCompact && width > 2 ? 2 : width) as 1 | 2 | 3 | 4,
            lineStyle:        dash ? LineStyle.Dashed : LineStyle.Solid,
            axisLabelVisible: true,
            title:            isCompact ? label : `${label} ${formatPrice(val)}`,
          });
        });

        // Fibonacci extension targets as LineSeries (autoscale includes them
        // even when T2/T3 are above the most recent candle range).
        FIB_EXT_CONFIG.forEach(({ key, color, width, label, ratio }) => {
          const val = signal[key];
          if (val == null) return;
          const s = chart.addSeries(LineSeries, {
            color,
            lineWidth:        width as 1 | 2 | 3 | 4,
            lineStyle:        LineStyle.Solid,
            priceLineVisible: false,
            lastValueVisible: true,
            title: isCompact ? label : `${label} ${ratio}  ${formatPrice(val)}`,
          });
          s.setData([
            { time: firstTime, value: val },
            { time: lastTime,  value: val },
          ]);
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
