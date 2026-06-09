"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useSelector, useDispatch } from "react-redux";
import {
  Box, Typography, Card, CardContent, Grid, TextField, Button,
  CircularProgress, Alert, Table, TableBody, TableCell,
  TableHead, TableRow, TableContainer, Chip, Stack,
  LinearProgress, Divider, Skeleton, Tooltip,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { enqueueSnackbar } from "notistack";
import { API_URL } from "@/lib/constants";
import { formatPrice, formatCompact } from "@/lib/formatters";
import type { RootState } from "@/store";
import type { AppDispatch } from "@/store";
import {
  backtestLiveReset,
  backtestLiveLoad,
} from "@/store/slices/wsSlice";

// ── Types ─────────────────────────────────────────────────────────────────────

type BtResult = {
  id: string; status: string; started_at: string;
  start_date: string; end_date: string;
  initial_capital: number;
  final_equity: number | null; total_trades: number | null;
  winning_trades: number | null; win_rate: number | null;
  cagr: number | null; sharpe_ratio: number | null; max_drawdown: number | null;
  total_symbols: number | null; scanned_symbols: number | null;
  error_message?: string;
};

type Trade = {
  id: string; symbol: string; entry_date: string; exit_date: string | null;
  entry_price: number; exit_price: number | null;
  timeframe: string; category: string; exit_reason: string | null;
  pnl_abs: number | null; pnl_pct: number | null; // decimal: 0.15 = 15%
  holding_days: number;
};

type EquityPoint = { curve_date: string; equity: number };

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
  bt, onLoad, onStop, onReattach,
}: {
  bt: BtResult;
  onLoad: (id: string) => void;
  onStop?: (id: string) => void;
  onReattach?: (bt: BtResult) => void;
}) {
  const totalReturn = bt.final_equity != null
    ? ((bt.final_equity - bt.initial_capital) / bt.initial_capital * 100)
    : null;
  const isLive       = bt.status === "running" || bt.status === "pending";
  const canLoad      = bt.status === "done";
  const canReattach  = isLive && !!onReattach;
  const isClickable  = canLoad || canReattach;
  const canStop      = onStop && isLive;
  const chipColor =
    bt.status === "done"        ? "success"
    : bt.status === "failed"    ? "error"
    : bt.status === "cancelled" ? "warning"
    : "info";
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 2, py: 0.75, px: 1, borderRadius: 1 }}>
      <Box
        onClick={() => {
          if (canLoad) onLoad(bt.id);
          else if (canReattach) onReattach!(bt);
        }}
        sx={{
          display: "flex", alignItems: "center", gap: 2, flex: 1,
          cursor: isClickable ? "pointer" : "default",
          "&:hover": isClickable ? { bgcolor: "action.hover" } : {},
          borderRadius: 1, py: 0.25, px: 0.5,
        }}
      >
        <Chip
          label={isLive ? bt.status : bt.status}
          size="small"
          color={chipColor as "success" | "error" | "warning" | "info" | "default"}
          sx={{
            minWidth: 78, fontSize: "0.68rem",
            ...(isLive && {
              animation: "pulse 1.6s ease-in-out infinite",
              "@keyframes pulse": {
                "0%, 100%": { opacity: 1 },
                "50%": { opacity: 0.55 },
              },
            }),
          }}
        />
        <Typography variant="body2" color="text.secondary" sx={{ minWidth: 160 }}>
          {bt.start_date} → {bt.end_date}
        </Typography>
        <Typography variant="body2">{formatCompact(bt.initial_capital)}</Typography>
        {totalReturn != null && (
          <Typography variant="body2" fontWeight={600}
            color={totalReturn >= 0 ? "success.main" : "error.main"}>
            {totalReturn >= 0 ? "+" : ""}{totalReturn.toFixed(1)}%
          </Typography>
        )}
        <Typography variant="caption" color="text.secondary" sx={{ ml: "auto", whiteSpace: "nowrap" }}>
          {isLive
            ? `${bt.scanned_symbols ?? 0}/${bt.total_symbols ?? "?"} stocks · click to watch`
            : `${bt.total_trades ?? "—"} trades · ${bt.started_at?.slice(0, 10)}`}
        </Typography>
      </Box>
      {canStop && (
        <Button
          size="small" variant="outlined" color="error"
          startIcon={<StopIcon sx={{ fontSize: 14 }} />}
          onClick={(e) => { e.stopPropagation(); onStop!(bt.id); }}
          sx={{ minWidth: 80, fontSize: "0.7rem", py: 0.25 }}
        >
          Stop
        </Button>
      )}
    </Box>
  );
}

// ── Constants ─────────────────────────────────────────────────────────────────

const MIN_CAPITAL           = 5_000;
const MAX_BACKTEST_ATTEMPTS = 240;
const BACKTEST_HISTORY_LIMIT = 5;
const MAX_TRADES_DISPLAYED   = 100;
const POLL_BASE_MS           = 5_000;
const POLL_BACKOFF_FACTOR    = 1.15;

// ── Main page ─────────────────────────────────────────────────────────────────

function todayISO() {
  return new Date().toISOString().split("T")[0];
}

export default function BacktestPage() {
  const dispatch = useDispatch<AppDispatch>();

  // Live streaming state from Redux
  const { stockResults: liveStockResults, progress: backtestProgress } =
    useSelector((s: RootState) => s.ws.backtestLive);

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
  // Inline per-symbol trades — fetched on demand when user clicks a stock row
  const [symbolTrades, setSymbolTrades]         = useState<Trade[]>([]);
  const [symbolTradesLoading, setSymbolTradesLoading] = useState(false);

  const pollRef         = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timerRef        = useRef<ReturnType<typeof setInterval> | null>(null);
  const inlineTradesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getJson(`${API_URL}/api/backtests`).then(setHistory).catch(() => {});
    return () => {
      if (pollRef.current)  clearTimeout(pollRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Fetch per-symbol trades whenever the selected stock changes
  useEffect(() => {
    if (!selectedSymbol) { setSymbolTrades([]); return; }
    // Use activeBacktestId during scan, fall back to loaded result id after completion
    const btId = activeBacktestId ?? result?.id;
    if (!btId) { setSymbolTrades([]); return; }
    setSymbolTradesLoading(true);
    getJson(`${API_URL}/api/backtests/${btId}/trades?symbol=${selectedSymbol}`)
      .then(setSymbolTrades)
      .catch(() => setSymbolTrades([]))
      .finally(() => setSymbolTradesLoading(false));
  }, [selectedSymbol, activeBacktestId, result?.id]);

  // Scroll inline trades card into view whenever it appears or changes symbol
  useEffect(() => {
    if (selectedSymbol && inlineTradesRef.current) {
      setTimeout(() => {
        inlineTradesRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }, 80);
    }
  }, [selectedSymbol]);

  const loadBacktest = useCallback(async (id: string, clearSelection = true) => {
    const [bt, curve, trs, stockRes] = await Promise.all([
      getJson(`${API_URL}/api/backtests/${id}`),
      getJson(`${API_URL}/api/backtests/${id}/equity-curve`).catch(() => []),
      getJson(`${API_URL}/api/backtests/${id}/trades`),
      getJson(`${API_URL}/api/backtests/${id}/stock-results`).catch(() => []),
    ]);
    setResult(bt);
    setEquityCurve(curve);
    setTrades(trs);
    // Only clear selection when user manually loads a different run from history.
    // Auto-loads (on completion) preserve selection so filtered trades render immediately.
    if (clearSelection) setSelectedSymbol(null);
    // Populate live per-stock table from DB for completed runs
    if (stockRes.length > 0) {
      dispatch(backtestLiveLoad({ backtest_id: id, results: stockRes }));
    }
  }, [dispatch]);

  // Shared polling logic — used by handleRun and handleReattach
  const startPolling = useCallback((backtest_id: string) => {
    let attempts = 0;
    const schedulePoll = () => {
      const delay = attempts < 10
        ? POLL_BASE_MS
        : Math.min(POLL_BASE_MS * Math.pow(POLL_BACKOFF_FACTOR, attempts - 10), 30_000);
      pollRef.current = setTimeout(async () => {
        attempts++;
        try {
          const bt: BtResult = await getJson(`${API_URL}/api/backtests/${backtest_id}`);
          if (bt.status === "done") {
            clearInterval(timerRef.current!);
            await loadBacktest(backtest_id, false);
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
              : "Polling stopped — backtest may still be running. Check Recent Backtests for updates.";
            setError(msg);
            setRunning(false); setActiveBacktestId(null);
          } else {
            schedulePoll();
          }
        } catch {
          schedulePoll();
        }
      }, delay);
    };
    schedulePoll();
  }, [loadBacktest]);

  // Re-attach to a running/pending backtest from Recent Backtests
  const handleReattach = useCallback(async (bt: BtResult) => {
    if (pollRef.current)  clearTimeout(pollRef.current);
    if (timerRef.current) clearInterval(timerRef.current);
    setError("");
    setRunning(true); setResult(null);
    setEquityCurve([]); setTrades([]); setElapsed(0);
    setActiveBacktestId(bt.id); setSelectedSymbol(null); setSymbolTrades([]);
    setCancelling(false);

    // Load partial results already recorded for this run
    dispatch(backtestLiveReset(bt.id));
    const stockRes = await getJson(`${API_URL}/api/backtests/${bt.id}/stock-results`).catch(() => []);
    if (stockRes.length > 0) {
      dispatch(backtestLiveLoad({ backtest_id: bt.id, results: stockRes }));
    }

    timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    startPolling(bt.id);
    enqueueSnackbar("Watching running backtest — results will update live", { variant: "info" });
  }, [dispatch, startPolling]);

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
    setActiveBacktestId(null); setSelectedSymbol(null); setSymbolTrades([]);
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
      dispatch(backtestLiveReset(backtest_id));
      enqueueSnackbar("Backtest queued — results will stream as each stock completes", { variant: "info" });
      startPolling(backtest_id);
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

  // Derived stats from result (shown in metric cards after completion)
  const totalReturn = result?.final_equity != null
    ? ((result.final_equity - result.initial_capital) / result.initial_capital * 100)
    : null;
  const wins    = result?.winning_trades ?? 0;
  const losses  = (result?.total_trades ?? 0) - wins;
  const totalPnl = trades.reduce((s, t) => s + (t.pnl_abs ?? 0), 0);
  const pnlValues = trades.map(t => t.pnl_abs).filter((v): v is number => v != null);
  const bestTrade  = pnlValues.length ? Math.max(...pnlValues) : null;
  const worstTrade = pnlValues.length ? Math.min(...pnlValues) : null;
  const holdingDays = trades.map(t => t.holding_days).filter((v): v is number => v != null && v >= 0);
  const avgHold = holdingDays.length
    ? holdingDays.reduce((s, d) => s + d, 0) / holdingDays.length
    : null;
  const universeCount = universe.trim()
    ? universe.split(",").filter(s => s.trim()).length
    : null;

  const filteredTrades = selectedSymbol
    ? trades.filter(t => t.symbol === selectedSymbol)
    : trades;

  // Sort live results: by total_pnl_abs desc (once stable); during scan keep append order
  const sortedLiveResults = running
    ? liveStockResults
    : [...liveStockResults].sort((a, b) => b.total_pnl_abs - a.total_pnl_abs);

  const showLiveTable = liveStockResults.length > 0 || (running && backtestProgress != null);

  return (
    <Box>
      <Typography variant="h6" fontWeight={700} mb={0.5}>Backtest Runner</Typography>
      <Typography variant="body2" color="text.secondary" mb={2}>
        Walk-forward simulation of the GATE pipeline. Each bar sees only past data — no look-ahead.
        Results stream stock-by-stock as each batch completes.
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

      {/* ── Progress indicator (live, determinate) ────────────────────────── */}
      {running && (
        <Card sx={{ mb: 2 }}>
          <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1 }}>
              <Typography variant="body2" color="text.secondary" sx={{ flex: 1, mr: 2 }} noWrap>
                {backtestProgress
                  ? `Scanning: ${backtestProgress.currentBatch.slice(0, 5).join(", ")}${backtestProgress.currentBatch.length > 5 ? "…" : ""}`
                  : "Queued — waiting for worker…"}
              </Typography>
              <Box display="flex" alignItems="center" gap={1.5} flexShrink={0}>
                {backtestProgress ? (
                  <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
                    {backtestProgress.completed} / {backtestProgress.total} stocks
                  </Typography>
                ) : (
                  <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
                    {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")} elapsed
                  </Typography>
                )}
                {activeBacktestId && (
                  <Button
                    size="small" variant="outlined" color="error"
                    startIcon={cancelling
                      ? <CircularProgress size={12} color="inherit" />
                      : <StopIcon sx={{ fontSize: 16 }} />}
                    onClick={() => handleStop(activeBacktestId)}
                    disabled={cancelling}
                    sx={{ whiteSpace: "nowrap" }}
                  >
                    Stop Scan
                  </Button>
                )}
              </Box>
            </Box>
            <LinearProgress
              variant={backtestProgress ? "determinate" : "indeterminate"}
              value={backtestProgress
                ? Math.round((backtestProgress.completed / backtestProgress.total) * 100)
                : undefined}
            />
          </CardContent>
        </Card>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>
      )}

      {/* ── Live per-stock results (shown during AND after scan) ────────────── */}
      {showLiveTable && (
        <Card sx={{ mb: 2 }}>
          <CardContent sx={{ pb: "12px !important" }}>
            <Box display="flex" alignItems="center" gap={1} mb={1} flexWrap="wrap">
              <Typography variant="subtitle2">Per Stock Results</Typography>
              {backtestProgress && (
                <Chip
                  label={`${liveStockResults.length} of ${backtestProgress.total}`}
                  size="small"
                  color={running ? "info" : "default"}
                />
              )}
              {!backtestProgress && liveStockResults.length > 0 && (
                <Chip label={`${liveStockResults.length} stocks`} size="small" />
              )}
              {selectedSymbol && (
                <Chip
                  label={`Filtered: ${selectedSymbol}`}
                  size="small" color="primary"
                  onDelete={() => setSelectedSymbol(null)}
                  sx={{ fontSize: "0.68rem" }}
                />
              )}
              <Typography variant="caption" color="text.secondary" sx={{ ml: "auto" }}>
                {running
                  ? "Results stream as each batch completes — click a row to pre-select"
                  : "Click a row to filter trades ↓"}
              </Typography>
            </Box>

            <TableContainer sx={{ maxHeight: 340 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    {["Symbol", "Status", "Trades", "Wins", "Win Rate", "Total P&L ₹", "Avg %", "Best %", "Worst %", "Avg Hold"].map(h => (
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
                  {/* Skeleton row for currently scanning batch */}
                  {running && backtestProgress?.currentBatch.map(sym => {
                    const alreadyDone = liveStockResults.some(r => r.symbol === sym);
                    if (alreadyDone) return null;
                    return (
                      <TableRow key={`scanning-${sym}`}>
                        <TableCell sx={{ fontWeight: 700, fontSize: "0.78rem" }}>
                          <Box display="flex" alignItems="center" gap={0.5}>
                            <CircularProgress size={10} />
                            <span>{sym}</span>
                          </Box>
                        </TableCell>
                        {Array.from({ length: 9 }).map((_, i) => (
                          <TableCell key={i}>
                            <Skeleton variant="text" width={40} />
                          </TableCell>
                        ))}
                      </TableRow>
                    );
                  })}

                  {/* Completed stock rows */}
                  {sortedLiveResults.map(s => {
                    const isSelected = selectedSymbol === s.symbol;
                    const isFailed   = s.status === "failed";
                    const rowBg = isSelected
                      ? "rgba(99,102,241,0.12)"
                      : isFailed
                        ? "rgba(239,68,68,0.06)"
                        : s.total_pnl_abs >= 0
                          ? "rgba(34,197,94,0.04)"
                          : "rgba(239,68,68,0.04)";
                    return (
                      <TableRow
                        key={s.symbol}
                        hover
                        onClick={() => !isFailed && setSelectedSymbol(isSelected ? null : s.symbol)}
                        sx={{
                          cursor: isFailed ? "default" : "pointer",
                          bgcolor: rowBg,
                          ...(isSelected && { outline: "1px solid rgba(99,102,241,0.4)" }),
                        }}
                      >
                        <TableCell sx={{ fontWeight: 700, fontSize: "0.78rem" }}>{s.symbol}</TableCell>
                        <TableCell>
                          {isFailed ? (
                            <Tooltip title={s.error ?? "scan failed"} placement="right">
                              <Chip label="failed" size="small" color="error" sx={{ fontSize: "0.65rem", height: 18 }} />
                            </Tooltip>
                          ) : (
                            <Chip label={s.category ?? "done"} size="small" variant="outlined"
                              sx={{ fontSize: "0.65rem", height: 18 }} />
                          )}
                        </TableCell>
                        <TableCell sx={{ fontSize: "0.75rem" }}>{isFailed ? "—" : s.total_trades}</TableCell>
                        <TableCell sx={{ fontSize: "0.75rem", color: "success.main" }}>{isFailed ? "—" : s.winning_trades}</TableCell>
                        <TableCell>
                          {isFailed ? "—" : (
                            <Typography variant="inherit" fontSize="0.75rem" fontWeight={600}
                              color={s.win_rate >= 50 ? "success.main" : "error.main"}>
                              {s.win_rate.toFixed(1)}%
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          {isFailed ? "—" : (
                            <Typography variant="inherit" fontSize="0.75rem" fontWeight={600}
                              color={s.total_pnl_abs >= 0 ? "success.main" : "error.main"}>
                              {s.total_pnl_abs >= 0 ? "+" : ""}{formatPrice(s.total_pnl_abs)}
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          {isFailed ? "—" : (
                            <Typography variant="inherit" fontSize="0.75rem"
                              color={s.avg_pnl_pct >= 0 ? "success.main" : "error.main"}>
                              {s.avg_pnl_pct >= 0 ? "+" : ""}{s.avg_pnl_pct.toFixed(1)}%
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell sx={{ fontSize: "0.75rem", color: "success.main" }}>
                          {isFailed ? "—" : `+${s.best_trade_pct.toFixed(1)}%`}
                        </TableCell>
                        <TableCell sx={{ fontSize: "0.75rem", color: "error.main" }}>
                          {isFailed ? "—" : `${s.worst_trade_pct.toFixed(1)}%`}
                        </TableCell>
                        <TableCell sx={{ fontSize: "0.72rem", color: "text.secondary" }}>
                          {isFailed ? "—" : `${s.avg_holding_days.toFixed(0)}d`}
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

      {/* ── Inline per-symbol trades (appears immediately on click) ─────────── */}
      {selectedSymbol && (
        <Card sx={{ mb: 2 }} ref={inlineTradesRef}>
          <CardContent>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1, flexWrap: "wrap" }}>
              <Typography variant="subtitle2">
                Trades — {selectedSymbol}
              </Typography>
              {symbolTradesLoading
                ? <CircularProgress size={14} />
                : <Chip label={symbolTrades.length} size="small" />}
              <Chip
                label="Clear"
                size="small" variant="outlined"
                onDelete={() => setSelectedSymbol(null)}
                onClick={() => setSelectedSymbol(null)}
                sx={{ fontSize: "0.68rem" }}
              />
              {running && (
                <Typography variant="caption" color="text.secondary" sx={{ ml: "auto" }}>
                  Showing trades recorded so far — updates as scan progresses
                </Typography>
              )}
            </Box>

            {symbolTradesLoading ? (
              <Box sx={{ py: 3, textAlign: "center" }}>
                <CircularProgress size={24} />
              </Box>
            ) : symbolTrades.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: "center" }}>
                {running
                  ? `No trades recorded for ${selectedSymbol} yet — batch may not have completed`
                  : `No trades recorded for ${selectedSymbol} in this period`}
              </Typography>
            ) : (
              <TableContainer sx={{ maxHeight: 360 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      {["TF", "Category", "Entry Date", "Exit Date", "Entry ₹", "Exit ₹", "P&L ₹", "P&L %", "Hold", "Exit Reason"].map(h => (
                        <TableCell key={h} sx={{ bgcolor: "background.paper", color: "text.secondary", fontSize: "0.72rem", whiteSpace: "nowrap" }}>
                          {h}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {symbolTrades.map((t, i) => {
                      const isWin  = (t.pnl_abs ?? 0) >= 0;
                      const pnlPct = t.pnl_pct != null ? t.pnl_pct * 100 : null;
                      return (
                        <TableRow key={t.id ?? i} hover>
                          <TableCell sx={{ color: "text.secondary", fontSize: "0.72rem" }}>{t.timeframe}</TableCell>
                          <TableCell>
                            <Chip label={t.category ?? "—"} size="small" variant="outlined" sx={{ fontSize: "0.65rem", height: 18 }} />
                          </TableCell>
                          <TableCell sx={{ fontSize: "0.72rem", color: "text.secondary", whiteSpace: "nowrap" }}>{t.entry_date}</TableCell>
                          <TableCell sx={{ fontSize: "0.72rem", color: "text.secondary", whiteSpace: "nowrap" }}>{t.exit_date ?? "—"}</TableCell>
                          <TableCell sx={{ fontSize: "0.75rem" }}>{formatPrice(t.entry_price)}</TableCell>
                          <TableCell sx={{ fontSize: "0.75rem" }}>{formatPrice(t.exit_price)}</TableCell>
                          <TableCell>
                            <Typography variant="inherit" fontSize="0.75rem" fontWeight={600} color={isWin ? "success.main" : "error.main"}>
                              {formatPrice(t.pnl_abs)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="inherit" fontSize="0.75rem" color={isWin ? "success.main" : "error.main"}>
                              {pnlPct != null ? `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(1)}%` : "—"}
                            </Typography>
                          </TableCell>
                          <TableCell sx={{ fontSize: "0.72rem", color: "text.secondary" }}>{t.holding_days}d</TableCell>
                          <TableCell sx={{ fontSize: "0.72rem", color: "text.secondary" }}>{t.exit_reason ?? "—"}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── History (shown when no live result loaded) ────────────────────── */}
      {!result && !showLiveTable && history.length > 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent sx={{ pb: "12px !important" }}>
            <Typography variant="subtitle2" mb={0.5}>Recent Backtests</Typography>
            <Typography variant="caption" color="text.secondary" display="block" mb={1}>
              Click a completed run to reload its results
            </Typography>
            {history.slice(0, BACKTEST_HISTORY_LIMIT).map(bt => (
              <HistoryRow key={bt.id} bt={bt} onLoad={loadBacktest} onStop={handleStop} onReattach={handleReattach} />
            ))}
          </CardContent>
        </Card>
      )}

      {/* History shown alongside live table when results loaded */}
      {(result || showLiveTable) && history.length > 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent sx={{ pb: "12px !important" }}>
            <Typography variant="subtitle2" mb={0.5}>Recent Backtests</Typography>
            {history.slice(0, BACKTEST_HISTORY_LIMIT).map(bt => (
              <HistoryRow key={bt.id} bt={bt} onLoad={loadBacktest} onStop={handleStop} onReattach={handleReattach} />
            ))}
          </CardContent>
        </Card>
      )}

      {/* ── Empty state ────────────────────────────────────────────────────── */}
      {!running && !result && !showLiveTable && history.length === 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent sx={{ textAlign: "center", py: 5 }}>
            <Typography variant="body2" color="text.secondary" fontWeight={600} gutterBottom>
              No backtests run yet
            </Typography>
            <Typography variant="caption" color="text.disabled" display="block" mb={2}>
              Configure a date range above and click Run Backtest to simulate the GATE strategy
              on historical data. Results stream stock-by-stock as each batch of 10 symbols completes.
            </Typography>
            <Stack direction="row" spacing={3} justifyContent="center">
              {[
                { label: "Win Rate",     value: "—" },
                { label: "Total P&L",    value: "—" },
                { label: "Total Trades", value: "—" },
                { label: "Stocks Scanned", value: "—" },
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

      {/* ── Results (shown after completion) ──────────────────────────────── */}
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
                label="Win Rate"
                value={result.win_rate != null ? `${(result.win_rate * 100).toFixed(1)}%` : "—"}
                sub={`${wins}W · ${losses}L`}
                sentiment={result.win_rate != null ? (result.win_rate >= 0.5 ? "positive" : "negative") : "neutral"}
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <MetricCard
                label="Total Trades"
                value={result.total_trades?.toString() ?? "—"}
                sentiment="neutral"
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <MetricCard
                label="Stocks Scanned"
                value={result.scanned_symbols != null ? `${result.scanned_symbols}` : (result.total_symbols?.toString() ?? "—")}
                sub={result.total_symbols ? `of ${result.total_symbols}` : undefined}
                sentiment="neutral"
              />
            </Grid>
            <Grid item xs={6} sm={4} md={2}>
              <MetricCard
                label="Total P&L"
                value={formatPrice(totalPnl)}
                sentiment={totalPnl >= 0 ? "positive" : "negative"}
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

          {/* Equity curve (only shown for runs that have one) */}
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

          {/* Full trades table — all stocks, filterable by selectedSymbol */}
          {trades.length > 0 ? (
            <Card>
              <CardContent>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1, flexWrap: "wrap" }}>
                  <Typography variant="subtitle2">
                    {selectedSymbol ? `All Trades — filtered to ${selectedSymbol}` : "All Trades"}
                  </Typography>
                  <Chip label={filteredTrades.length} size="small" />
                  {selectedSymbol && (
                    <Chip
                      label="Show all"
                      size="small" variant="outlined"
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
                      {filteredTrades.slice(0, MAX_TRADES_DISPLAYED).map((t, i) => {
                        const isWin  = (t.pnl_abs ?? 0) >= 0;
                        const pnlPct = t.pnl_pct != null ? t.pnl_pct * 100 : null;
                        return (
                          <TableRow key={t.id ?? i} hover>
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
