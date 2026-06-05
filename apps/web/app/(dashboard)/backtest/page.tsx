"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import {
  Box, Typography, Card, CardContent, Grid, TextField, Button,
  CircularProgress, Alert, Table, TableBody, TableCell,
  TableHead, TableRow, TableContainer, Chip, Stack,
  LinearProgress, Divider,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { enqueueSnackbar } from "notistack";
import { API_URL } from "@/lib/constants";
import { formatPrice, formatCompact } from "@/lib/formatters";

// ── Types ─────────────────────────────────────────────────────────────────────

type BtResult = {
  id: string; status: string; started_at: string;
  start_date: string; end_date: string;
  initial_capital: number;
  final_equity: number | null; total_trades: number | null;
  winning_trades: number | null; win_rate: number | null;
  cagr: number | null; sharpe_ratio: number | null; max_drawdown: number | null;
  error_message?: string;
};

type Trade = {
  id: string; symbol: string; entry_date: string; exit_date: string | null;
  entry_price: number; exit_price: number | null;
  timeframe: string; category: string; exit_reason: string | null;
  pnl_abs: number | null; pnl_pct: number | null; // pnl_pct is decimal: 0.15 = 15%
  holding_days: number;
};

type EquityPoint = { curve_date: string; equity: number };

type StockStat = {
  symbol:      string;
  category:    string;
  totalTrades: number;
  wins:        number;
  winRate:     number;
  totalPnlAbs: number;
  avgPnlPct:   number;
  bestPct:     number;
  worstPct:    number;
  avgHoldDays: number;
};

// ── API helpers ───────────────────────────────────────────────────────────────

async function postJson(url: string, body: object) {
  const res = await fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function getJson(url: string) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Metric card ───────────────────────────────────────────────────────────────

function MetricCard({
  label, value, sub, sentiment,
}: {
  label: string; value: string; sub?: string;
  sentiment?: "positive" | "negative" | "neutral";
}) {
  const borderColor = sentiment === "positive" ? "success.main"
    : sentiment === "negative" ? "error.main" : "divider";
  const textColor = sentiment === "positive" ? "success.main"
    : sentiment === "negative" ? "error.main" : "text.primary";
  return (
    <Card sx={{ height: "100%", borderLeft: "3px solid", borderColor }}>
      <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Typography variant="caption" color="text.secondary" display="block" noWrap>
          {label}
        </Typography>
        <Typography variant="h6" fontWeight={700} color={textColor}>{value}</Typography>
        {sub && <Typography variant="caption" color="text.secondary">{sub}</Typography>}
      </CardContent>
    </Card>
  );
}

// ── History row ───────────────────────────────────────────────────────────────

function HistoryRow({
  bt, onLoad, onStop,
}: {
  bt: BtResult;
  onLoad: (id: string) => void;
  onStop?: (id: string) => void;
}) {
  const totalReturn = bt.final_equity != null
    ? ((bt.final_equity - bt.initial_capital) / bt.initial_capital * 100)
    : null;
  const canLoad = bt.status === "done";
  const canStop = onStop && (bt.status === "pending" || bt.status === "running");
  const chipColor =
    bt.status === "done"      ? "success"
    : bt.status === "failed"  ? "error"
    : bt.status === "cancelled" ? "warning"
    : "default";
  return (
    <Box
      sx={{
        display: "flex", alignItems: "center", gap: 2, py: 0.75, px: 1,
        borderRadius: 1,
      }}
    >
      <Box
        onClick={() => canLoad && onLoad(bt.id)}
        sx={{
          display: "flex", alignItems: "center", gap: 2, flex: 1,
          cursor: canLoad ? "pointer" : "default",
          "&:hover": canLoad ? { bgcolor: "action.hover" } : {},
          borderRadius: 1, py: 0.25, px: 0.5,
        }}
      >
        <Chip
          label={bt.status} size="small"
          color={chipColor as any}
          sx={{ minWidth: 78, fontSize: "0.68rem" }}
        />
        <Typography variant="body2" color="text.secondary" sx={{ minWidth: 160 }}>
          {bt.start_date} → {bt.end_date}
        </Typography>
        <Typography variant="body2">{formatCompact(bt.initial_capital)}</Typography>
        {totalReturn != null && (
          <Typography variant="body2" fontWeight={600}
            color={totalReturn >= 0 ? "success.main" : "error.main"}
          >
            {totalReturn >= 0 ? "+" : ""}{totalReturn.toFixed(1)}%
          </Typography>
        )}
        <Typography variant="caption" color="text.secondary" sx={{ ml: "auto", whiteSpace: "nowrap" }}>
          {bt.total_trades ?? "—"} trades · {bt.started_at?.slice(0, 10)}
        </Typography>
      </Box>
      {canStop && (
        <Button
          size="small" variant="outlined" color="error"
          startIcon={<StopIcon sx={{ fontSize: 14 }} />}
          onClick={(e) => { e.stopPropagation(); onStop(bt.id); }}
          sx={{ minWidth: 80, fontSize: "0.7rem", py: 0.25 }}
        >
          Stop
        </Button>
      )}
    </Box>
  );
}

// ── Constants ─────────────────────────────────────────────────────────────────

const MIN_CAPITAL          = 5_000;
const MAX_BACKTEST_ATTEMPTS = 240;   // 240 × 5s base = 20 min ceiling
const BACKTEST_HISTORY_LIMIT = 5;
const MAX_TRADES_DISPLAYED   = 100;
const POLL_BASE_MS           = 5_000;
const POLL_BACKOFF_FACTOR    = 1.15;  // interval grows ~15% per attempt after 10 tries

// ── Main page ─────────────────────────────────────────────────────────────────

function todayISO() {
  return new Date().toISOString().split("T")[0];
}

export default function BacktestPage() {
  const [startDate, setStartDate] = useState("2022-01-01");
  const [endDate, setEndDate]     = useState(todayISO);
  const [capital, setCapital]     = useState("1000000");
  const [universe, setUniverse]   = useState("");
  const [running, setRunning]     = useState(false);
  const [result, setResult]       = useState<BtResult | null>(null);
  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([]);
  const [trades, setTrades]       = useState<Trade[]>([]);
  const [error, setError]         = useState("");
  const [elapsed, setElapsed]     = useState(0);
  const [history, setHistory]     = useState<BtResult[]>([]);
  const [activeBacktestId, setActiveBacktestId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

  const pollRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getJson(`${API_URL}/api/backtests`).then(setHistory).catch(() => {});
    return () => {
      if (pollRef.current)  clearTimeout(pollRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const loadBacktest = useCallback(async (id: string) => {
    const [bt, curve, trs] = await Promise.all([
      getJson(`${API_URL}/api/backtests/${id}`),
      getJson(`${API_URL}/api/backtests/${id}/equity-curve`),
      getJson(`${API_URL}/api/backtests/${id}/trades`),
    ]);
    setResult(bt);
    setEquityCurve(curve);
    setTrades(trs);
  }, []);

  const handleRun = async () => {
    setError("");
    if (!startDate) { setError("Start Date is required."); return; }
    if (!endDate)   { setError("End Date is required."); return; }
    if (endDate <= startDate) { setError("End Date must be after Start Date."); return; }
    const cap = parseFloat(capital);
    if (!capital || isNaN(cap) || cap < MIN_CAPITAL) {
      setError(`Capital must be at least ₹${MIN_CAPITAL.toLocaleString("en-IN")}.`); return;
    }

    setRunning(true); setResult(null);
    setEquityCurve([]); setTrades([]); setElapsed(0);
    setActiveBacktestId(null); setSelectedSymbol(null);
    timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    try {
      const universeList = universe.trim()
        ? universe.split(",").map(s => s.trim().toUpperCase()).filter(Boolean)
        : [];
      const { backtest_id } = await postJson(`${API_URL}/api/backtests/run`, {
        start_date: startDate, end_date: endDate || null,
        initial_capital: cap, universe: universeList,
      });
      setActiveBacktestId(backtest_id);
      enqueueSnackbar("Backtest queued — this may take 5–15 minutes for large universes", { variant: "info" });
      let attempts = 0;
      const schedulePoll = () => {
        // Exponential backoff: base 5s, grows ~15% per attempt after 10, capped at 30s
        const delay = attempts < 10
          ? POLL_BASE_MS
          : Math.min(POLL_BASE_MS * Math.pow(POLL_BACKOFF_FACTOR, attempts - 10), 30_000);
        pollRef.current = setTimeout(async () => {
          attempts++;
          try {
            const bt: BtResult = await getJson(`${API_URL}/api/backtests/${backtest_id}`);
            if (bt.status === "done") {
              clearInterval(timerRef.current!);
              await loadBacktest(backtest_id);
              setRunning(false); setActiveBacktestId(null);
              getJson(`${API_URL}/api/backtests`).then(setHistory).catch(() => {});
              enqueueSnackbar("Backtest complete!", { variant: "success" });
            } else if (bt.status === "cancelled") {
              clearInterval(timerRef.current!);
              setRunning(false); setActiveBacktestId(null);
              getJson(`${API_URL}/api/backtests`).then(setHistory).catch(() => {});
              enqueueSnackbar("Backtest stopped.", { variant: "warning" });
            } else if (bt.status === "failed" || attempts > MAX_BACKTEST_ATTEMPTS) {
              clearInterval(timerRef.current!);
              const msg = bt.status === "failed"
                ? (bt.error_message ?? "Backtest failed — check the worker logs for details")
                : "Backtest is taking longer than expected (>20 min). It may still be running — check Recent Backtests later.";
              setError(msg);
              setRunning(false); setActiveBacktestId(null);
            } else {
              schedulePoll();
            }
          } catch {
            // Transient network error — keep polling
            schedulePoll();
          }
        }, delay);
      };
      schedulePoll();
    } catch (err) {
      clearInterval(timerRef.current!);
      setError(String(err)); setRunning(false); setActiveBacktestId(null);
    }
  };

  const handleStop = async (id: string) => {
    if (cancelling) return;
    setCancelling(true);
    try {
      await postJson(`${API_URL}/api/backtests/${id}/cancel`, {});
      if (pollRef.current) clearTimeout(pollRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
      setRunning(false); setActiveBacktestId(null);
      getJson(`${API_URL}/api/backtests`).then(setHistory).catch(() => {});
      enqueueSnackbar("Backtest stopped.", { variant: "warning" });
    } catch {
      enqueueSnackbar("Could not stop backtest — it may have already finished.", { variant: "info" });
    } finally {
      setCancelling(false);
    }
  };

  // Derived stats
  const totalReturn = result?.final_equity != null
    ? ((result.final_equity - result.initial_capital) / result.initial_capital * 100)
    : null;
  const wins       = result?.winning_trades ?? 0;
  const losses     = (result?.total_trades ?? 0) - wins;
  const totalPnl   = trades.reduce((s, t) => s + (t.pnl_abs ?? 0), 0);
  const pnlValues  = trades.map(t => t.pnl_abs).filter((v): v is number => v != null);
  const bestTrade  = pnlValues.length ? Math.max(...pnlValues) : null;
  const worstTrade = pnlValues.length ? Math.min(...pnlValues) : null;
  // avgHold: only count closed trades that have a recorded holding_days
  const holdingDays = trades.map(t => t.holding_days).filter((v): v is number => v != null && v >= 0);
  const avgHold     = holdingDays.length
    ? holdingDays.reduce((s, d) => s + d, 0) / holdingDays.length
    : null;
  const universeCount = universe.trim()
    ? universe.split(",").filter(s => s.trim()).length
    : null;

  // Per-stock breakdown computed from the trades array
  const perStockStats: StockStat[] = (() => {
    if (!trades.length) return [];
    const map = new Map<string, { trades: Trade[] }>();
    for (const t of trades) {
      if (!map.has(t.symbol)) map.set(t.symbol, { trades: [] });
      map.get(t.symbol)!.trades.push(t);
    }
    return Array.from(map.entries()).map(([symbol, { trades: st }]) => {
      const wins = st.filter(t => (t.pnl_abs ?? 0) > 0).length;
      const pnlVals = st.map(t => t.pnl_abs ?? 0);
      const pctVals = st.map(t => (t.pnl_pct ?? 0) * 100);
      const holdVals = st.map(t => t.holding_days ?? 0).filter(v => v >= 0);
      const catCounts: Record<string, number> = {};
      st.forEach(t => { if (t.category) catCounts[t.category] = (catCounts[t.category] ?? 0) + 1; });
      const category = Object.entries(catCounts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—";
      return {
        symbol,
        category,
        totalTrades: st.length,
        wins,
        winRate: Math.round((wins / st.length) * 100),
        totalPnlAbs: pnlVals.reduce((s, v) => s + v, 0),
        avgPnlPct: pctVals.length ? pctVals.reduce((s, v) => s + v, 0) / pctVals.length : 0,
        bestPct: pctVals.length ? Math.max(...pctVals) : 0,
        worstPct: pctVals.length ? Math.min(...pctVals) : 0,
        avgHoldDays: holdVals.length ? holdVals.reduce((s, v) => s + v, 0) / holdVals.length : 0,
      } satisfies StockStat;
    }).sort((a, b) => b.totalPnlAbs - a.totalPnlAbs);
  })();

  const filteredTrades = selectedSymbol
    ? trades.filter(t => t.symbol === selectedSymbol)
    : trades;

  return (
    <Box>
      <Typography variant="h6" fontWeight={700} mb={0.5}>Backtest Runner</Typography>
      <Typography variant="body2" color="text.secondary" mb={2}>
        Walk-forward simulation of the GATE pipeline. Each bar sees only past data — no look-ahead.
      </Typography>

      {/* ── Config form ───────────────────────────────────────────────────── */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="flex-start">
            <Grid item xs={6} sm={2}>
              <TextField
                label="Start Date" type="date" size="small" fullWidth
                value={startDate} onChange={e => setStartDate(e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={6} sm={2}>
              <TextField
                label="End Date" type="date" size="small" fullWidth
                value={endDate} onChange={e => setEndDate(e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={2}>
              <TextField
                label="Capital (₹)" type="number" size="small" fullWidth
                value={capital} onChange={e => setCapital(e.target.value)}
                inputProps={{ min: 10000, step: 50000 }}
                helperText={capital ? formatCompact(parseFloat(capital)) : ""}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                label="Universe" size="small" fullWidth
                value={universe} onChange={e => setUniverse(e.target.value)}
                placeholder="RELIANCE,TCS,HDFCBANK  (blank = default)"
                helperText={
                  universeCount
                    ? `${universeCount} symbol${universeCount !== 1 ? "s" : ""} specified`
                    : "Default: Nifty 50 + Next 50 + Midcap 150"
                }
              />
            </Grid>
            <Grid item xs={12} sm={2}>
              <Button
                variant="contained" fullWidth onClick={handleRun} disabled={running || cancelling}
                startIcon={running ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
                sx={{ height: 40 }}
              >
                {running ? "Running…" : "Run Backtest"}
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* ── Progress indicator ─────────────────────────────────────────────── */}
      {running && (
        <Card sx={{ mb: 2 }}>
          <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1 }}>
              <Typography variant="body2" color="text.secondary">
                Fetching data · computing signals · running walk-forward engine…
              </Typography>
              <Box display="flex" alignItems="center" gap={1.5} ml={2}>
                <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
                  {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")} elapsed
                </Typography>
                {activeBacktestId && (
                  <Button
                    size="small" variant="outlined" color="error"
                    startIcon={cancelling ? <CircularProgress size={12} color="inherit" /> : <StopIcon sx={{ fontSize: 16 }} />}
                    onClick={() => handleStop(activeBacktestId)}
                    disabled={cancelling}
                    sx={{ whiteSpace: "nowrap" }}
                  >
                    Stop Scan
                  </Button>
                )}
              </Box>
            </Box>
            <LinearProgress variant="indeterminate" />
          </CardContent>
        </Card>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>
      )}

      {/* ── History (always shown unless a fresh result just loaded) ─────── */}
      {!result && history.length > 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent sx={{ pb: "12px !important" }}>
            <Typography variant="subtitle2" mb={0.5}>Recent Backtests</Typography>
            <Typography variant="caption" color="text.secondary" display="block" mb={1}>
              Click a completed run to reload its results
            </Typography>
            {history.slice(0, BACKTEST_HISTORY_LIMIT).map(bt => (
              <HistoryRow key={bt.id} bt={bt} onLoad={loadBacktest} onStop={handleStop} />
            ))}
          </CardContent>
        </Card>
      )}

      {/* ── Empty state — no runs yet ──────────────────────────────────────── */}
      {!running && !result && history.length === 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent sx={{ textAlign: "center", py: 5 }}>
            <Typography variant="body2" color="text.secondary" fontWeight={600} gutterBottom>
              No backtests run yet
            </Typography>
            <Typography variant="caption" color="text.disabled" display="block" mb={2}>
              Configure a date range above and click Run Backtest to simulate the GATE strategy
              on historical data. The walk-forward engine uses no look-ahead — each bar only sees past data.
            </Typography>
            <Stack direction="row" spacing={3} justifyContent="center">
              {[
                { label: "Win Rate",     value: "—" },
                { label: "CAGR",         value: "—" },
                { label: "Max Drawdown", value: "—" },
                { label: "Total Trades", value: "—" },
              ].map(({ label, value }) => (
                <Box key={label} textAlign="center">
                  <Typography variant="caption" color="text.disabled" display="block">{label}</Typography>
                  <Typography variant="h6" color="text.disabled">{value}</Typography>
                </Box>
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}

      {/* ── Results ───────────────────────────────────────────────────────── */}
      {result && (
        <>
          {/* Metric cards */}
          <Grid container spacing={2} mb={2}>
            <Grid item xs={6} sm={4} md={2}>
              <MetricCard
                label="Final Equity"
                value={formatCompact(result.final_equity)}
                sub={`started ${formatCompact(result.initial_capital)}`}
                sentiment={totalReturn != null ? (totalReturn >= 0 ? "positive" : "negative") : "neutral"}
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <MetricCard
                label="Total Return"
                value={totalReturn != null ? `${totalReturn >= 0 ? "+" : ""}${totalReturn.toFixed(1)}%` : "—"}
                sentiment={totalReturn != null ? (totalReturn >= 0 ? "positive" : "negative") : "neutral"}
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <MetricCard
                label="CAGR"
                value={result.cagr != null ? `${(result.cagr * 100).toFixed(1)}%` : "—"}
                sentiment={result.cagr != null ? (result.cagr >= 0 ? "positive" : "negative") : "neutral"}
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <MetricCard
                label="Win Rate"
                value={result.win_rate != null ? `${(result.win_rate * 100).toFixed(1)}%` : "—"}
                sub={`${wins}W · ${losses}L`}
                sentiment={result.win_rate != null ? (result.win_rate >= 0.5 ? "positive" : "negative") : "neutral"}
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <MetricCard
                label="Sharpe Ratio"
                value={result.sharpe_ratio != null ? result.sharpe_ratio.toFixed(2) : "—"}
                sentiment={
                  result.sharpe_ratio == null ? "neutral"
                  : result.sharpe_ratio >= 1 ? "positive"
                  : result.sharpe_ratio >= 0 ? "neutral"
                  : "negative"
                }
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <MetricCard
                label="Max Drawdown"
                value={result.max_drawdown != null ? `${(result.max_drawdown * 100).toFixed(1)}%` : "—"}
                sentiment="negative"
              />
            </Grid>
          </Grid>

          {/* Trade summary strip */}
          {trades.length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
                <Stack
                  direction="row" spacing={3} flexWrap="wrap" useFlexGap
                  divider={<Divider orientation="vertical" flexItem />}
                >
                  {[
                    { label: "Total P&L",   value: formatPrice(totalPnl),                     pos: totalPnl >= 0 ? "positive" : "negative" },
                    { label: "Avg Hold",    value: avgHold ? `${avgHold.toFixed(1)} days` : "—", pos: "neutral" },
                    { label: "Best Trade",  value: bestTrade  != null ? formatPrice(bestTrade)  : "—", pos: "positive" },
                    { label: "Worst Trade", value: worstTrade != null ? formatPrice(worstTrade) : "—", pos: "negative" },
                  ].map(({ label, value, pos }) => (
                    <Box key={label} sx={{ py: 0.5 }}>
                      <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
                      <Typography
                        variant="body2" fontWeight={600}
                        color={pos === "positive" ? "success.main" : pos === "negative" ? "error.main" : "text.primary"}
                      >
                        {value}
                      </Typography>
                    </Box>
                  ))}
                </Stack>
              </CardContent>
            </Card>
          )}

          {/* Per Stock Results */}
          {perStockStats.length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent sx={{ pb: "12px !important" }}>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <Typography variant="subtitle2">Per Stock Results</Typography>
                  <Chip label={`${perStockStats.length} stocks`} size="small" />
                  {selectedSymbol && (
                    <Chip
                      label={`Filtered: ${selectedSymbol}`}
                      size="small"
                      color="primary"
                      onDelete={() => setSelectedSymbol(null)}
                      sx={{ fontSize: "0.68rem" }}
                    />
                  )}
                  <Typography variant="caption" color="text.secondary" sx={{ ml: "auto" }}>
                    Click a row to filter the trade list
                  </Typography>
                </Box>
                <TableContainer sx={{ maxHeight: 320 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        {["Symbol", "Category", "Trades", "Wins", "Win Rate", "Total P&L ₹", "Avg P&L %", "Best %", "Worst %", "Avg Hold"].map(h => (
                          <TableCell
                            key={h}
                            sx={{ bgcolor: "background.paper", color: "text.secondary", fontSize: "0.72rem", whiteSpace: "nowrap" }}
                          >
                            {h}
                          </TableCell>
                        ))}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {perStockStats.map(s => {
                        const isSelected = selectedSymbol === s.symbol;
                        const rowBg = isSelected
                          ? "rgba(99,102,241,0.12)"
                          : s.totalPnlAbs >= 0
                            ? "rgba(34,197,94,0.04)"
                            : "rgba(239,68,68,0.04)";
                        return (
                          <TableRow
                            key={s.symbol}
                            hover
                            onClick={() => setSelectedSymbol(isSelected ? null : s.symbol)}
                            sx={{ cursor: "pointer", bgcolor: rowBg,
                              ...(isSelected && { outline: "1px solid rgba(99,102,241,0.4)" }) }}
                          >
                            <TableCell sx={{ fontWeight: 700, fontSize: "0.78rem" }}>{s.symbol}</TableCell>
                            <TableCell>
                              <Chip label={s.category} size="small" variant="outlined" sx={{ fontSize: "0.65rem", height: 18 }} />
                            </TableCell>
                            <TableCell sx={{ fontSize: "0.75rem" }}>{s.totalTrades}</TableCell>
                            <TableCell sx={{ fontSize: "0.75rem", color: "success.main" }}>{s.wins}</TableCell>
                            <TableCell>
                              <Typography variant="inherit" fontSize="0.75rem" fontWeight={600}
                                color={s.winRate >= 50 ? "success.main" : "error.main"}>
                                {s.winRate}%
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography variant="inherit" fontSize="0.75rem" fontWeight={600}
                                color={s.totalPnlAbs >= 0 ? "success.main" : "error.main"}>
                                {s.totalPnlAbs >= 0 ? "+" : ""}{formatPrice(s.totalPnlAbs)}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography variant="inherit" fontSize="0.75rem"
                                color={s.avgPnlPct >= 0 ? "success.main" : "error.main"}>
                                {s.avgPnlPct >= 0 ? "+" : ""}{s.avgPnlPct.toFixed(1)}%
                              </Typography>
                            </TableCell>
                            <TableCell sx={{ fontSize: "0.75rem", color: "success.main" }}>
                              +{s.bestPct.toFixed(1)}%
                            </TableCell>
                            <TableCell sx={{ fontSize: "0.75rem", color: "error.main" }}>
                              {s.worstPct.toFixed(1)}%
                            </TableCell>
                            <TableCell sx={{ fontSize: "0.72rem", color: "text.secondary" }}>
                              {s.avgHoldDays.toFixed(0)}d
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          )}

          {/* Equity curve */}
          {equityCurve.length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="subtitle2" mb={1}>Equity Curve</Typography>
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart data={equityCurve} margin={{ left: 8, right: 16 }}>
                    <defs>
                      <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.35} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis
                      dataKey="curve_date" stroke="#64748b"
                      tick={{ fontSize: 10 }} interval="preserveStartEnd"
                    />
                    <YAxis
                      stroke="#64748b" tick={{ fontSize: 10 }} width={72}
                      tickFormatter={v => formatCompact(v)}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1a1a24",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: 8,
                      }}
                      formatter={(v: number) => [formatCompact(v), "Equity"]}
                      labelStyle={{ color: "#94a3b8", fontSize: 11 }}
                    />
                    <ReferenceLine
                      y={result.initial_capital} stroke="#f59e0b" strokeDasharray="4 4"
                      label={{ value: "Invested", fill: "#f59e0b", fontSize: 9, position: "insideTopRight" }}
                    />
                    <Area
                      type="monotone" dataKey="equity"
                      stroke="#6366f1" fill="url(#eqGrad)"
                      strokeWidth={2} dot={false} activeDot={{ r: 4 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Trades table */}
          {trades.length > 0 ? (
            <Card>
              <CardContent>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1, flexWrap: "wrap" }}>
                  <Typography variant="subtitle2">
                    {selectedSymbol ? `Trades — ${selectedSymbol}` : "Trades"}
                  </Typography>
                  <Chip label={filteredTrades.length} size="small" />
                  {selectedSymbol && (
                    <Chip
                      label="Clear filter"
                      size="small"
                      variant="outlined"
                      onDelete={() => setSelectedSymbol(null)}
                      onClick={() => setSelectedSymbol(null)}
                      sx={{ fontSize: "0.68rem" }}
                    />
                  )}
                  {filteredTrades.length > MAX_TRADES_DISPLAYED && (
                    <Typography variant="caption" color="text.secondary">
                      (showing first {MAX_TRADES_DISPLAYED})
                    </Typography>
                  )}
                </Box>
                <TableContainer sx={{ maxHeight: 420 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        {["Symbol", "TF", "Category", "Entry", "Exit", "Entry ₹", "Exit ₹", "P&L ₹", "P&L %", "Hold", "Exit Reason"].map(h => (
                          <TableCell
                            key={h}
                            sx={{ bgcolor: "background.paper", color: "text.secondary", fontSize: "0.72rem", whiteSpace: "nowrap" }}
                          >
                            {h}
                          </TableCell>
                        ))}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {filteredTrades.slice(0, MAX_TRADES_DISPLAYED).map(t => {
                        const isWin  = (t.pnl_abs ?? 0) >= 0;
                        const pnlPct = t.pnl_pct != null ? t.pnl_pct * 100 : null;
                        return (
                          <TableRow key={t.id} hover>
                            <TableCell sx={{ fontWeight: 600, fontSize: "0.78rem" }}>{t.symbol}</TableCell>
                            <TableCell sx={{ color: "text.secondary", fontSize: "0.72rem" }}>{t.timeframe}</TableCell>
                            <TableCell>
                              <Chip label={t.category ?? "—"} size="small" variant="outlined"
                                sx={{ fontSize: "0.65rem", height: 18 }} />
                            </TableCell>
                            <TableCell sx={{ fontSize: "0.72rem", color: "text.secondary", whiteSpace: "nowrap" }}>
                              {t.entry_date}
                            </TableCell>
                            <TableCell sx={{ fontSize: "0.72rem", color: "text.secondary", whiteSpace: "nowrap" }}>
                              {t.exit_date ?? "—"}
                            </TableCell>
                            <TableCell sx={{ fontSize: "0.75rem" }}>{formatPrice(t.entry_price)}</TableCell>
                            <TableCell sx={{ fontSize: "0.75rem" }}>{formatPrice(t.exit_price)}</TableCell>
                            <TableCell>
                              <Typography variant="inherit" fontSize="0.75rem" fontWeight={600}
                                color={isWin ? "success.main" : "error.main"}>
                                {formatPrice(t.pnl_abs)}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography variant="inherit" fontSize="0.75rem"
                                color={isWin ? "success.main" : "error.main"}>
                                {pnlPct != null ? `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(1)}%` : "—"}
                              </Typography>
                            </TableCell>
                            <TableCell sx={{ fontSize: "0.72rem", color: "text.secondary" }}>
                              {t.holding_days}d
                            </TableCell>
                            <TableCell sx={{ fontSize: "0.72rem", color: "text.secondary" }}>
                              {t.exit_reason ?? "—"}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          ) : result.status === "done" && (
            <Card>
              <CardContent sx={{ textAlign: "center", py: 4 }}>
                <Typography color="text.secondary">No trades generated for this period and universe.</Typography>
                <Typography variant="caption" color="text.secondary" display="block" mt={0.5}>
                  Try a wider date range or leave the universe blank to use the default.
                </Typography>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </Box>
  );
}
