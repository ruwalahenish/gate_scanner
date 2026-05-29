"use client";
import {
  Box, Typography, Grid, Card, CardContent, CircularProgress,
} from "@mui/material";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, PieChart, Pie, Cell, Legend,
} from "recharts";
import { useGetPortfolioSummaryQuery, useGetTradesQuery } from "@/store/api/portfolioApi";
import { StatCard } from "@/components/ui/StatCard";
import { formatPrice, formatPct } from "@/lib/formatters";

const CHART_COLORS = ["#22c55e", "#ef4444", "#6366f1", "#f59e0b"];

function MonthlyPnlChart({ trades }: { trades: { pnl_abs?: number; executed_at?: string }[] }) {
  // Group closed trades by month
  const monthly: Record<string, number> = {};
  trades.forEach((t) => {
    if (!t.pnl_abs || !t.executed_at) return;
    const date = new Date(t.executed_at);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    monthly[key] = (monthly[key] ?? 0) + t.pnl_abs;
  });
  const data = Object.entries(monthly)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, pnl]) => ({ month, pnl: Math.round(pnl) }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="month" stroke="#94a3b8" tick={{ fontSize: 11 }} />
        <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
        <Tooltip
          contentStyle={{ backgroundColor: "#1a1a24", border: "1px solid rgba(255,255,255,0.1)" }}
          labelStyle={{ color: "#f1f5f9" }}
          formatter={(v: number) => [formatPrice(v), "P&L"]}
        />
        <Bar dataKey="pnl" radius={[3, 3, 0, 0]}>
          {data.map((entry, index) => (
            <Cell key={index} fill={entry.pnl >= 0 ? "#22c55e" : "#ef4444"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function WinLossDonut({ winning, total }: { winning: number; total: number }) {
  const losing = total - winning;
  const data = [
    { name: "Winners", value: winning },
    { name: "Losers", value: losing },
  ];
  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={80}
          dataKey="value"
          label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
          labelLine={false}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={CHART_COLORS[i]} />
          ))}
        </Pie>
        <Tooltip contentStyle={{ backgroundColor: "#1a1a24", border: "1px solid rgba(255,255,255,0.1)" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export default function AnalyticsPage() {
  const { data: summary } = useGetPortfolioSummaryQuery();
  const { data: tradesData, isLoading } = useGetTradesQuery({ limit: 200 });
  const trades = tradesData?.items ?? [];
  const closedTrades = trades.filter((t) => t.pnl_abs != null);

  if (isLoading) return <CircularProgress sx={{ m: 4 }} />;

  return (
    <Box>
      <Typography variant="h6" fontWeight={700} mb={2}>Analytics</Typography>

      {/* Key metrics */}
      <Grid container spacing={2} mb={3}>
        {[
          { label: "Total Trades", value: summary?.total_trades ?? 0 },
          { label: "Win Rate", value: `${summary?.win_rate?.toFixed(1) ?? "—"}%` },
          { label: "Realized P&L", value: formatPrice(summary?.realized_pnl) },
          { label: "Unrealized P&L", value: formatPrice(summary?.unrealized_pnl) },
        ].map((item) => (
          <Grid item xs={6} sm={3} key={item.label}>
            <StatCard label={item.label} value={item.value} />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2}>
        {/* Monthly P&L bar chart */}
        <Grid item xs={12} md={7}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>Monthly P&L</Typography>
              {closedTrades.length > 0 ? (
                <MonthlyPnlChart trades={closedTrades} />
              ) : (
                <Typography color="text.secondary" variant="body2">No closed trades yet</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Win/Loss donut */}
        <Grid item xs={12} md={5}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>Win / Loss Split</Typography>
              {(summary?.total_trades ?? 0) > 0 ? (
                <WinLossDonut
                  winning={summary?.winning_trades ?? 0}
                  total={summary?.total_trades ?? 0}
                />
              ) : (
                <Typography color="text.secondary" variant="body2">No trades yet</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Trade stats table */}
        {closedTrades.length > 0 && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>Performance Metrics</Typography>
                <Grid container spacing={2}>
                  {[
                    ["Avg Win", formatPrice(
                      closedTrades.filter((t) => (t.pnl_abs ?? 0) > 0).reduce((s, t) => s + (t.pnl_abs ?? 0), 0)
                      / Math.max(summary?.winning_trades ?? 1, 1)
                    )],
                    ["Avg Loss", formatPrice(
                      Math.abs(closedTrades.filter((t) => (t.pnl_abs ?? 0) < 0).reduce((s, t) => s + (t.pnl_abs ?? 0), 0)
                      / Math.max((summary?.total_trades ?? 0) - (summary?.winning_trades ?? 0), 1))
                    )],
                    ["Best Trade", formatPrice(Math.max(...closedTrades.map((t) => t.pnl_abs ?? 0)))],
                    ["Worst Trade", formatPrice(Math.min(...closedTrades.map((t) => t.pnl_abs ?? 0)))],
                  ].map(([label, value]) => (
                    <Grid item xs={6} sm={3} key={String(label)}>
                      <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
                      <Typography variant="body1" fontWeight={600}>{value}</Typography>
                    </Grid>
                  ))}
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}
