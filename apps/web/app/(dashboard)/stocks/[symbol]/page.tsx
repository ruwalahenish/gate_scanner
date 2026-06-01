"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Box, Typography, Grid, Chip, Button, Tabs, Tab,
  Select, MenuItem, FormControl, Stack, Divider,
  CircularProgress, Paper, Tooltip,
} from "@mui/material";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import { ArrowBack, Refresh, TrendingUp, TrendingDown } from "@mui/icons-material";
import { GATEChart } from "@/components/domain/GATEChart";
import { GATEBar } from "@/components/ui/GATEBar";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { StatCard } from "@/components/ui/StatCard";
import { formatPrice, formatPct, formatRR, formatScore, formatIST, formatCompact } from "@/lib/formatters";
import {
  useGetStockQuery,
  useGetStockChartDataQuery,
  useGetStockAnalysisQuery,
  useGetStockBacktestTradesQuery,
} from "@/store/api/stockMasterApi";
import { useGetPriceQuery } from "@/store/api/marketApi";
import type { BacktestTrade } from "@/types/stock";

const TIMEFRAMES = [
  { value: "1d",  label: "Daily" },
  { value: "1wk", label: "Weekly" },
  { value: "1mo", label: "Monthly" },
  { value: "4h",  label: "4 Hour" },
  { value: "60m", label: "1 Hour" },
  { value: "15m", label: "15 Min" },
];

const BACKTEST_COLUMNS: GridColDef<BacktestTrade>[] = [
  {
    field: "entry_date",
    headerName: "Entry",
    width: 100,
    renderCell: (p) => <Typography variant="caption">{p.value?.slice(0, 10)}</Typography>,
  },
  {
    field: "exit_date",
    headerName: "Exit",
    width: 100,
    renderCell: (p) => <Typography variant="caption">{p.value?.slice(0, 10) ?? "—"}</Typography>,
  },
  {
    field: "entry_price",
    headerName: "Buy",
    width: 80,
    renderCell: (p) => <Typography variant="caption">{formatPrice(p.value)}</Typography>,
  },
  {
    field: "exit_price",
    headerName: "Sell",
    width: 80,
    renderCell: (p) => <Typography variant="caption">{p.value ? formatPrice(p.value) : "—"}</Typography>,
  },
  {
    field: "pnl_pct",
    headerName: "P&L %",
    width: 80,
    renderCell: (p) =>
      p.value != null ? (
        <Typography
          variant="caption"
          fontWeight={600}
          color={p.value >= 0 ? "success.main" : "error.main"}
        >
          {formatPct(p.value)}
        </Typography>
      ) : <Typography variant="caption" color="text.disabled">—</Typography>,
  },
  {
    field: "rr_achieved",
    headerName: "RR",
    width: 60,
    renderCell: (p) =>
      p.value != null ? (
        <Typography variant="caption" color={p.value >= 1.5 ? "success.main" : "text.secondary"}>
          {formatRR(p.value)}
        </Typography>
      ) : <Typography variant="caption" color="text.disabled">—</Typography>,
  },
  {
    field: "holding_days",
    headerName: "Days",
    width: 55,
    renderCell: (p) => <Typography variant="caption">{p.value ?? "—"}</Typography>,
  },
  {
    field: "exit_reason",
    headerName: "Exit Reason",
    width: 120,
    renderCell: (p) => (
      <Typography variant="caption" color="text.secondary">{p.value ?? "—"}</Typography>
    ),
  },
  {
    field: "backtest_date",
    headerName: "Backtest",
    width: 130,
    renderCell: (p) => <Typography variant="caption" color="text.disabled">{formatIST(p.value)}</Typography>,
  },
];

function LevelRow({ label, value, color }: { label: string; value: number | null; color?: string }) {
  return (
    <Box display="flex" justifyContent="space-between" alignItems="center" py={0.5}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="body2" fontWeight={600} sx={{ color: color ?? "text.primary", fontVariantNumeric: "tabular-nums" }}>
        {value ? formatPrice(value) : "—"}
      </Typography>
    </Box>
  );
}

export default function StockDetailPage() {
  const params = useParams<{ symbol: string }>();
  const router = useRouter();
  const symbol = (params.symbol ?? "").toUpperCase();

  const [tab, setTab] = useState(0);
  const [timeframe, setTimeframe] = useState("1d");
  const [analysisTriggered, setAnalysisTriggered] = useState(false);

  const { data: stock } = useGetStockQuery(symbol);
  const { data: priceData } = useGetPriceQuery(symbol, { pollingInterval: 60_000 });
  const { data: chartData, isFetching: chartLoading } = useGetStockChartDataQuery(
    { symbol, timeframe },
    { skip: tab !== 0 },
  );
  const { data: analysisData, isFetching: analysisLoading } = useGetStockAnalysisQuery(symbol, {
    skip: !analysisTriggered && tab !== 1,
  });
  const { data: tradeHistory, isLoading: tradesLoading } = useGetStockBacktestTradesQuery(
    { symbol, limit: 100 },
    { skip: tab !== 2 },
  );

  // Extract signal levels for chart overlay
  const sig = (analysisData as any)?.signal ?? null;
  const signalLevels = sig
    ? { entry: sig.entry, stop_loss: sig.stop_loss, t1: sig.T1, t2: sig.T2, t3: sig.T3 }
    : stock?.latest_entry
      ? { entry: stock.latest_entry, stop_loss: stock.latest_stop_loss, t1: stock.latest_t1 }
      : null;

  const perTf: Record<string, any> = (analysisData as any)?.per_tf ?? {};
  const summary: Record<string, any> = (analysisData as any)?.summary ?? {};

  // Backtest summary stats
  const trades = tradeHistory ?? [];
  const closedTrades = trades.filter((t) => t.pnl_pct != null);
  const winRate = closedTrades.length
    ? Math.round((closedTrades.filter((t) => (t.pnl_pct ?? 0) > 0).length / closedTrades.length) * 100)
    : null;
  const avgPnl = closedTrades.length
    ? closedTrades.reduce((s, t) => s + (t.pnl_pct ?? 0), 0) / closedTrades.length
    : null;

  return (
    <Box>
      {/* Header */}
      <Box display="flex" alignItems="center" gap={1.5} mb={2.5}>
        <Button
          startIcon={<ArrowBack />}
          size="small"
          onClick={() => router.push("/stocks")}
          sx={{ minWidth: "auto" }}
        >
          Stocks
        </Button>
        <Divider orientation="vertical" flexItem />
        <Box flex={1}>
          <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
            <Typography variant="h6" fontWeight={700} color="primary.light">
              {symbol}
            </Typography>
            {stock?.company_name && (
              <Typography variant="body2" color="text.secondary">
                · {stock.company_name}
              </Typography>
            )}
            {stock?.sector && (
              <Chip label={stock.sector} size="small" variant="outlined" sx={{ fontSize: 11 }} />
            )}
            {stock?.latest_category && (
              <CategoryChip category={stock.latest_category as import("@/types/signal").SignalCategory} />
            )}
          </Box>
          <Box display="flex" gap={2} mt={0.3}>
            {priceData?.price && (
              <Typography variant="body2" fontWeight={700} sx={{ fontVariantNumeric: "tabular-nums" }}>
                {formatPrice(priceData.price)}
              </Typography>
            )}
            {stock?.market_cap && (
              <Typography variant="body2" color="text.secondary">
                MCap: {formatCompact(stock.market_cap)}
              </Typography>
            )}
            {stock?.pe_ratio && (
              <Typography variant="body2" color="text.secondary">
                PE: {stock.pe_ratio.toFixed(1)}
              </Typography>
            )}
            {stock?.is_fno && <Chip label="F&O" size="small" color="primary" sx={{ height: 18, fontSize: 10 }} />}
            {stock?.in_nifty50 && <Chip label="Nifty 50" size="small" color="success" sx={{ height: 18, fontSize: 10 }} />}
          </Box>
        </Box>
      </Box>

      {/* Tabs */}
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2, borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <Tab label="Chart" />
        <Tab label="GATE Analysis" />
        <Tab label="Backtest History" />
      </Tabs>

      {/* ── Tab 0: Chart ── */}
      {tab === 0 && (
        <Box>
          <Stack direction="row" alignItems="center" spacing={1.5} mb={1.5}>
            <FormControl size="small" sx={{ minWidth: 110 }}>
              <Select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
                {TIMEFRAMES.map((tf) => <MenuItem key={tf.value} value={tf.value}>{tf.label}</MenuItem>)}
              </Select>
            </FormControl>
            {stock?.latest_entry && (
              <Typography variant="caption" color="text.secondary">
                Levels from latest scan signal
              </Typography>
            )}
          </Stack>

          <Box sx={{ borderRadius: 2, overflow: "hidden", mb: 2 }}>
            <GATEChart
              bars={chartData?.bars ?? []}
              signal={signalLevels}
              loading={chartLoading}
              height={460}
            />
          </Box>

          {/* Signal levels panel */}
          {signalLevels && (
            <Paper sx={{ p: 2, bgcolor: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)" }}>
              <Typography variant="caption" color="text.secondary" display="block" mb={1} fontWeight={600}>
                {sig ? "Live Analysis Levels" : "Latest Scan Signal Levels"}
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <LevelRow label="Entry" value={signalLevels.entry ?? null} color="#6366f1" />
                  <LevelRow label="Stop Loss" value={signalLevels.stop_loss ?? null} color="#ef4444" />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <LevelRow label="Target 1" value={signalLevels.t1 ?? null} color="#4ade80" />
                  {(signalLevels as any).t2 && <LevelRow label="Target 2" value={(signalLevels as any).t2} color="#22c55e" />}
                  {(signalLevels as any).t3 && <LevelRow label="Target 3" value={(signalLevels as any).t3} color="#16a34a" />}
                </Grid>
                {stock?.latest_rr_t1 && (
                  <Grid item xs={12} sm={6} md={3}>
                    <Box display="flex" justifyContent="space-between" py={0.5}>
                      <Typography variant="caption" color="text.secondary">Risk:Reward (T1)</Typography>
                      <Typography variant="body2" fontWeight={700} color={stock.latest_rr_t1 >= 2 ? "success.main" : "text.primary"}>
                        {formatRR(stock.latest_rr_t1)}
                      </Typography>
                    </Box>
                  </Grid>
                )}
              </Grid>
            </Paper>
          )}
        </Box>
      )}

      {/* ── Tab 1: GATE Analysis ── */}
      {tab === 1 && (
        <Box>
          {!analysisTriggered && !analysisData ? (
            <Box textAlign="center" py={6}>
              <Typography color="text.secondary" mb={2}>
                Live GATE analysis runs the full multi-timeframe engine (~5 seconds).
              </Typography>
              <Button
                variant="contained"
                startIcon={<Refresh />}
                onClick={() => setAnalysisTriggered(true)}
              >
                Run Live Analysis
              </Button>
            </Box>
          ) : analysisLoading ? (
            <Box display="flex" justifyContent="center" alignItems="center" py={8} gap={2}>
              <CircularProgress size={24} />
              <Typography color="text.secondary">Running GATE engine…</Typography>
            </Box>
          ) : analysisData ? (
            <Box>
              {/* MTF summary */}
              {summary && (
                <Grid container spacing={2} mb={3}>
                  <Grid item xs={6} sm={3}>
                    <StatCard label="Leading TF" value={(summary as any).leading_tf ?? "—"} />
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <StatCard label="Confirm TF" value={(summary as any).confirmation_tf ?? "—"} />
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <StatCard
                      label="MTF Alignment"
                      value={`${Math.round(((summary as any).alignment?.alignment_pct ?? 0) * 100) / 100}%`}
                    />
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <StatCard
                      label="Structure Quality"
                      value={formatScore((summary as any).structure_quality)}
                    />
                  </Grid>
                </Grid>
              )}

              {/* Live signal panel */}
              {sig && (
                <Paper sx={{ p: 2, mb: 3, bgcolor: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)" }}>
                  <Box display="flex" alignItems="center" gap={1.5} mb={1.5}>
                    <Typography variant="subtitle2" fontWeight={700}>
                      Current Opportunity
                    </Typography>
                    {sig.category && <CategoryChip category={sig.category} />}
                    {sig.side === "BUY" ? (
                      <TrendingUp sx={{ color: "success.main", fontSize: 18 }} />
                    ) : sig.side === "SELL" ? (
                      <TrendingDown sx={{ color: "error.main", fontSize: 18 }} />
                    ) : null}
                  </Box>
                  <Grid container spacing={2}>
                    <Grid item xs={6} sm={3}>
                      <LevelRow label="Entry"     value={sig.entry}     color="#6366f1" />
                      <LevelRow label="Stop Loss" value={sig.stop_loss} color="#ef4444" />
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <LevelRow label="T1" value={sig.T1} color="#4ade80" />
                      <LevelRow label="T2" value={sig.T2} color="#22c55e" />
                      <LevelRow label="T3" value={sig.T3} color="#16a34a" />
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Box display="flex" justifyContent="space-between" py={0.5}>
                        <Typography variant="caption" color="text.secondary">GATE Strength</Typography>
                        <Typography variant="body2" fontWeight={600}>{formatScore(sig.gate_strength)}</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between" py={0.5}>
                        <Typography variant="caption" color="text.secondary">Confidence</Typography>
                        <Typography variant="body2" fontWeight={600}>{formatScore(sig.confidence)}</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Box display="flex" justifyContent="space-between" py={0.5}>
                        <Typography variant="caption" color="text.secondary">RR (T1)</Typography>
                        <Typography variant="body2" fontWeight={700} color="success.main">
                          {sig.rr?.T1 ? formatRR(sig.rr.T1) : "—"}
                        </Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between" py={0.5}>
                        <Typography variant="caption" color="text.secondary">Signal TF</Typography>
                        <Chip label={sig.signal_timeframe ?? "—"} size="small" sx={{ height: 18, fontSize: "0.68rem" }} />
                      </Box>
                    </Grid>
                  </Grid>
                </Paper>
              )}

              {/* Per-timeframe breakdown */}
              {Object.keys(perTf).length > 0 && (
                <Box>
                  <Typography variant="subtitle2" fontWeight={700} mb={1.5}>
                    Per-Timeframe Breakdown
                  </Typography>
                  <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 1.5 }}>
                    {Object.entries(perTf).map(([tf, data]: [string, any]) => (
                      <Paper key={tf} sx={{ p: 1.5, bgcolor: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
                        <Typography variant="caption" fontWeight={700} color="primary.light">{tf}</Typography>
                        <Box mt={0.5}>
                          {[
                            ["GATE Score", data.gate_score],
                            ["Breakout Prob", data.breakout_prob],
                            ["Trend", data.trend_direction],
                            ["EMA Stack", data.ema_stack],
                          ].map(([label, val]) => (
                            <Box key={String(label)} display="flex" justifyContent="space-between" py={0.2}>
                              <Typography variant="caption" color="text.secondary">{label}</Typography>
                              <Typography variant="caption" fontWeight={600}>
                                {typeof val === "number" ? formatScore(val) : (val ?? "—")}
                              </Typography>
                            </Box>
                          ))}
                        </Box>
                      </Paper>
                    ))}
                  </Box>
                </Box>
              )}

              <Box mt={2} display="flex" justifyContent="flex-end">
                <Button size="small" startIcon={<Refresh />} onClick={() => setAnalysisTriggered(true)}>
                  Re-run
                </Button>
              </Box>
            </Box>
          ) : null}
        </Box>
      )}

      {/* ── Tab 2: Backtest History ── */}
      {tab === 2 && (
        <Box>
          {/* Summary stats */}
          {trades.length > 0 && (
            <Grid container spacing={2} mb={2.5}>
              <Grid item xs={6} sm={3}>
                <StatCard label="Total Trades" value={closedTrades.length} />
              </Grid>
              <Grid item xs={6} sm={3}>
                <StatCard
                  label="Win Rate"
                  value={winRate != null ? `${winRate}%` : "—"}
                  color={winRate != null && winRate >= 50 ? "#22c55e" : "#ef4444"}
                />
              </Grid>
              <Grid item xs={6} sm={3}>
                <StatCard
                  label="Avg P&L"
                  value={avgPnl != null ? formatPct(avgPnl) : "—"}
                  color={avgPnl != null && avgPnl >= 0 ? "#22c55e" : "#ef4444"}
                />
              </Grid>
              <Grid item xs={6} sm={3}>
                <StatCard
                  label="Best Trade"
                  value={closedTrades.length ? formatPct(Math.max(...closedTrades.map((t) => t.pnl_pct ?? 0))) : "—"}
                  color="#22c55e"
                />
              </Grid>
            </Grid>
          )}

          {trades.length === 0 && !tradesLoading ? (
            <Box textAlign="center" py={6}>
              <Typography color="text.secondary">
                No backtest trades found for {symbol}. Run a backtest to see historical results.
              </Typography>
            </Box>
          ) : (
            <DataGrid
              rows={trades}
              columns={BACKTEST_COLUMNS}
              loading={tradesLoading}
              getRowId={(r) => `${r.backtest_id}-${r.entry_date}`}
              density="compact"
              hideFooterPagination={trades.length <= 25}
              pageSizeOptions={[25, 50, 100]}
              disableRowSelectionOnClick
              getRowClassName={(p) =>
                (p.row as BacktestTrade).pnl_pct != null
                  ? (p.row as BacktestTrade).pnl_pct! >= 0
                    ? "profitable-row"
                    : "loss-row"
                  : ""
              }
              sx={{
                border: "none",
                minHeight: 300,
                "& .profitable-row": { bgcolor: "rgba(34,197,94,0.04)" },
                "& .loss-row": { bgcolor: "rgba(239,68,68,0.04)" },
              }}
            />
          )}
        </Box>
      )}
    </Box>
  );
}
