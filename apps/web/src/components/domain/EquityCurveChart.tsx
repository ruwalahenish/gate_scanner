"use client";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { STATUS_COLORS } from "@/lib/constants";
import { formatCompact } from "@/lib/formatters";

export type EquityPoint = { curve_date: string; equity: number };

/**
 * Backtest equity curve. Loaded via next/dynamic so recharts stays out of the
 * page's initial bundle — it is only needed once a completed result is shown.
 */
export default function EquityCurveChart({
  data,
  initialCapital,
}: {
  data: EquityPoint[];
  initialCapital: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ left: 8, right: 16 }}>
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={STATUS_COLORS.SWING} stopOpacity={0.35} />
            <stop offset="95%" stopColor={STATUS_COLORS.SWING} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis
          dataKey="curve_date" stroke={STATUS_COLORS.IGNORE}
          tick={{ fontSize: 10 }} interval="preserveStartEnd"
        />
        <YAxis
          stroke={STATUS_COLORS.IGNORE} tick={{ fontSize: 10 }} width={72}
          tickFormatter={v => formatCompact(v)}
        />
        <RechartsTooltip
          contentStyle={{
            backgroundColor: "#1a1a24",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 8,
          }}
          formatter={(v: number) => [formatCompact(v), "Equity"]}
          labelStyle={{ color: "#94a3b8", fontSize: 11 }}
        />
        <ReferenceLine
          y={initialCapital} stroke={STATUS_COLORS.WATCH} strokeDasharray="4 4"
          label={{ value: "Invested", fill: STATUS_COLORS.WATCH, fontSize: 9, position: "insideTopRight" }}
        />
        <Area
          type="monotone" dataKey="equity"
          stroke={STATUS_COLORS.SWING} fill="url(#eqGrad)"
          strokeWidth={2} dot={false} activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
