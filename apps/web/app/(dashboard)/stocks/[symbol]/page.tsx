"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Box, Typography, Grid, Chip, Button, Tabs, Tab,
  Select, MenuItem, FormControl, Stack, Divider,
  CircularProgress, Paper,
} from "@mui/material";
import {
  ArrowBack, Refresh, ShowChart, Storage,
} from "@mui/icons-material";
import { GATEChart } from "@/components/domain/GATEChart";
import { TradeSetupPanel } from "@/components/domain/TradeSetupPanel";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { StatCard } from "@/components/ui/StatCard";
import { formatPrice, formatScore, formatCompact } from "@/lib/formatters";
import { fromSignal, fromLiveAnalysis, fromStockLatest, toChartLevels } from "@/lib/tradeSetup";
import {
  useGetStockQuery,
  useGetStockChartDataQuery,
  useGetStockAnalysisQuery,
} from "@/store/api/stockMasterApi";
import { useGetSignalHistoryQuery } from "@/store/api/signalsApi";
import { useGetPriceQuery } from "@/store/api/marketApi";

const TIMEFRAMES = [
  { value: "1d",  label: "Daily" },
  { value: "1wk", label: "Weekly" },
  { value: "1mo", label: "Monthly" },
  { value: "4h",  label: "4 Hour" },
  { value: "60m", label: "1 Hour" },
  { value: "15m", label: "15 Min" },
];

export default function StockDetailPage() {
  const params = useParams<{ symbol: string }>();
  const router = useRouter();
  const symbol = (params.symbol ?? "").toUpperCase();

  const [tab, setTab] = useState(0);
  const [timeframe, setTimeframe] = useState("1d");
  const [analysisTriggered, setAnalysisTriggered] = useState(false);

  const { data: stock } = useGetStockQuery(symbol);
  const { data: priceData } = useGetPriceQuery(symbol, { pollingInterval: 60_000, skipPollingIfUnfocused: true });
  // Fetch the latest stored signal (limit=1) so the chart gets breakout_level, t2, t3
  // that aren't available on the stock row's latest_* columns.
  const { data: signalHistory } = useGetSignalHistoryQuery({ symbol, limit: 1 });
  const { data: chartData, isFetching: chartLoading } = useGetStockChartDataQuery(
    { symbol, timeframe },
    { skip: tab !== 0 },
  );
  const { data: analysisData, isFetching: analysisLoading } = useGetStockAnalysisQuery(symbol, {
    skip: !analysisTriggered && tab !== 1,
  });

  // Canonical trade setup — live analysis takes precedence over the stored scan.
  const liveCategory = (stock?.latest_category as import("@/types/signal").SignalCategory) ?? null;
  const liveSetup = analysisData
    ? fromLiveAnalysis(symbol, analysisData, {
        category: liveCategory,
        // Detail-page live analysis is a fresh on-demand read → treat as confirmed-live.
        provenance: (analysisData as any)?.signal?.entry != null ? "confirmed" : "none",
      })
    : null;
  // Prefer the full stored signal (breakout_level, t2, t3 included) over the
  // partial stock-row snapshot (latest_* columns lack breakout_level, t2, t3).
  const latestStoredSignal = signalHistory?.[0] ?? null;
  const storedSetup = latestStoredSignal
    ? fromSignal(latestStoredSignal)
    : stock?.latest_entry != null ? fromStockLatest(stock) : null;
  const setup = liveSetup ?? storedSetup;
  const chartLevels = toChartLevels(setup);

  const perTf: Record<string, any> = (analysisData as any)?.per_tf ?? {};
  const summary: Record<string, any> = (analysisData as any)?.summary ?? {};

  return (
    <Box>
      {/* Header */}
      <Box display="flex" alignItems="center" gap={1.5} mb={2.5}>
        <Button
          startIcon={<ArrowBack />}
          size="small"
          onClick={() => (window.history.length > 1 ? router.back() : router.push("/stocks"))}
          aria-label="Go back"
          sx={{ minWidth: "auto" }}
        >
          Back
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

      {/* Data source legend */}
      <Stack direction="row" spacing={1} mb={1.5} flexWrap="wrap">
        <Chip
          icon={<ShowChart sx={{ fontSize: "14px !important" }} />}
          label="OHLCV & Live Price — yfinance"
          size="small"
          variant="outlined"
          sx={{ fontSize: "0.68rem", height: 22, borderColor: "rgba(99,102,241,0.4)", color: "text.secondary" }}
        />
        <Chip
          icon={<Storage sx={{ fontSize: "14px !important" }} />}
          label="Fundamentals (PE, ROCE, OPM, Shareholding) — Screener.in"
          size="small"
          variant="outlined"
          sx={{ fontSize: "0.68rem", height: 22, borderColor: "rgba(34,197,94,0.4)", color: "text.secondary" }}
        />
      </Stack>

      {/* Tabs */}
      <Tabs value={tab} onChange={(_, v) => setTab(v)} aria-label="Stock detail sections" sx={{ mb: 2, borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <Tab label="Chart" />
        <Tab label="GATE Analysis" />
      </Tabs>

      {/* ── Tab 0: Chart ── */}
      {tab === 0 && (
        <Box>
          <Stack direction="row" alignItems="center" spacing={1.5} mb={1.5}>
            <FormControl size="small" sx={{ minWidth: 110 }} aria-label="Chart timeframe">
              <Select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
                {TIMEFRAMES.map((tf) => <MenuItem key={tf.value} value={tf.value}>{tf.label}</MenuItem>)}
              </Select>
            </FormControl>
            {setup?.hasLevels && (
              <Typography variant="caption" color="text.secondary">
                {liveSetup ? "Levels from live analysis" : "Levels from latest scan signal"}
              </Typography>
            )}
          </Stack>

          <Box sx={{ borderRadius: 2, overflow: "hidden", mb: 2 }}>
            <ErrorBoundary>
              <GATEChart
                bars={chartData?.bars ?? []}
                signal={chartLevels}
                loading={chartLoading}
                height={460}
              />
            </ErrorBoundary>
          </Box>

          {/* Consolidated trade setup */}
          {setup && (
            <TradeSetupPanel
              setup={setup}
              variant="full"
              headerTitle={liveSetup ? "Live Analysis Levels" : "Latest Scan Signal"}
            />
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

              {/* Live signal panel (handles the "no setup yet" state internally) */}
              {liveSetup && (
                <Box mb={3}>
                  <TradeSetupPanel
                    setup={liveSetup}
                    variant="full"
                    headerTitle="Current Opportunity"
                  />
                </Box>
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
    </Box>
  );
}
