"use client";
import { useState, useMemo, useEffect, useRef, useCallback, memo } from "react";
import {
  Box, Card, CardContent, Grid, Typography, Chip, Tab, Tabs,
  LinearProgress, CircularProgress, Stack, Pagination,
  Button, Divider, Tooltip,
} from "@mui/material";
import {
  PlayArrow, Schedule, CheckCircleOutline,
  TrendingUp, Visibility, DoNotDisturbAlt, BarChart,
} from "@mui/icons-material";
import { PaperTradingPanel } from "@/components/domain/PaperTradingPanel";
import { BacktestPanel } from "@/components/domain/BacktestPanel";
import { useGetPositionsQuery } from "@/store/api/paperTradingApi";
import { useSelector, useDispatch } from "react-redux";
import { SignalTable } from "@/components/domain/SignalTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { StockLink } from "@/components/ui/StockLink";
import { PageError } from "@/components/ui/PageError";
import {
  useGetScanResultsQuery,
  useListScansQuery,
  useTriggerScanMutation,
  useStopScanMutation,
  useGetScanStatusQuery,
  useGetSignalCountsQuery,
  scannerApi,
} from "@/store/api/scannerApi";
import { useGetStockStatsQuery } from "@/store/api/stockMasterApi";
import { scanStarted, scanFailed, scanCompleted } from "@/store/slices/wsSlice";
import { formatIST, formatPrice } from "@/lib/formatters";
import { STATUS_COLORS, BUY_CATEGORIES, CATEGORY_DISPLAY } from "@/lib/constants";
import {
  selectScanProgress,
  selectScanStartedAt,
  selectCompletionSummary,
  selectCurrentScanId,
  selectStreamingSignals,
  selectStreamingBuyCount,
  selectStreamingWatchCount,
  selectStreamingNoActCount,
  selectScanPhaseMessage,
} from "@/store/selectors";
import type { AppDispatch } from "@/store";
import type { Signal, SignalCategory, DisplayStatus } from "@/types/signal";
import type { StreamingSignal } from "@/types/scan";
import type { CompletionSummary } from "@/store/slices/wsSlice";

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 50;

// The scanner always scans the full Master Stock List — no index-based universe
// filtering. (Universe selection was removed; mode is fixed to "full".)
const SCAN_MODE = "full";

// If a scan runs longer than this without completing, surface a "taking longer
// than expected" hint. We never auto-cancel — a full master scan can be slow.
const SLOW_SCAN_THRESHOLD_SEC = 8 * 60;

type FilterTab = "ALL" | "BUY" | "WATCH" | "NO_ACTION";

const TABS: { value: FilterTab; label: string; color: string }[] = [
  { value: "ALL",       label: "All",              color: "#94a3b8"                   },
  { value: "BUY",       label: "BUY Opportunity",  color: STATUS_COLORS.INVESTMENT    },
  { value: "WATCH",     label: "Watch",            color: STATUS_COLORS.WATCH         },
  { value: "NO_ACTION", label: "No Action",        color: STATUS_COLORS.IGNORE        },
];

const FEED_ROW_BASE_SX = {
  py: 0.4, px: 0.8, borderRadius: 1, bgcolor: "rgba(255,255,255,0.02)",
} as const;

const FEED_ROW_FIRST_SX = {
  ...FEED_ROW_BASE_SX,
  bgcolor: "rgba(99,102,241,0.08)",
} as const;

function tabChipSx(color: string, isActive: boolean) {
  return {
    height: 17,
    fontSize: "0.62rem",
    bgcolor: isActive ? `${color}30` : "rgba(255,255,255,0.06)",
    color: isActive ? color : "text.secondary",
    fontWeight: 600,
  } as const;
}

// ─────────────────────────────────────────────────────────────────────────────
// Convert StreamingSignal → Signal shape for table rendering
// ─────────────────────────────────────────────────────────────────────────────

function streamingToSignal(s: StreamingSignal, idx: number): Signal {
  const cat = s.category as SignalCategory;
  const meta = CATEGORY_DISPLAY[cat];
  return {
    id:                     `streaming-${idx}-${s.symbol}`,
    scan_id:                "streaming",
    symbol:                 s.symbol,
    category:               cat,
    display_status:         meta?.display ?? "NO_ACTION",
    display_category:       meta?.label   ?? "—",
    side:                   s.side,
    signal_timeframe:       s.signal_timeframe,
    sl_timeframe:           null,
    trend_direction:        null,
    entry:                  s.entry,
    stop_loss:              s.stop_loss,
    sl_distance_pct:        null,
    t1:                     s.t1,
    t2:                     s.t2,
    t3:                     s.t3,
    rr_t1:                  s.rr_t1,
    rr_t2:                  s.rr_t2,
    rr_t3:                  null,
    gate_strength:          s.gate_strength,
    volatility_compression: null,
    breakout_probability:   null,
    confidence:             s.confidence,
    rank_score:             s.rank_score,
    mtf_alignment_pct:      null,
    structure_quality:      null,
    atr:                    null,
    htf_confirmed:          s.htf_confirmed,
    correction_validated:   null,
    bounce_sequence_valid:  null,
    fib_confluence:         null,
    phase:                  null,
    trailing_plan:          null,
    reasoning:              null,
    breakout_state:         null,
    range_high:             null,
    range_low:              null,
    breakout_level:         null,
    measured_move:          null,
    rs_score:               null,
    sector_momentum:        null,
    accumulation_score:     null,
    fundamental_score:      null,
    volume_buildup:         null,
    created_at:             new Date().toISOString(),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Filter helpers
// ─────────────────────────────────────────────────────────────────────────────

function filterByTab(signals: Signal[], tab: FilterTab): Signal[] {
  if (tab === "ALL") return signals;
  return signals.filter((s) => s.display_status === tab);
}

function countByStatus(signals: Signal[]): Record<DisplayStatus, number> {
  return signals.reduce(
    (acc, s) => {
      const k = (s.display_status ?? "NO_ACTION") as DisplayStatus;
      acc[k] = (acc[k] ?? 0) + 1;
      return acc;
    },
    { BUY: 0, WATCH: 0, NO_ACTION: 0 } as Record<DisplayStatus, number>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatDuration(sec: number): string {
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function useElapsedSeconds(startedAt: number | null): number {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!startedAt) { setElapsed(0); return; }
    const tick = () => setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  return elapsed;
}

// ─────────────────────────────────────────────────────────────────────────────
// Rich scan detail panel (replaces thin banner)
// ─────────────────────────────────────────────────────────────────────────────

const PHASE_LABELS: Record<string, string> = {
  resolving_universe: "Resolving stock universe…",
  fetching_data:      "Fetching market data…",
  analyzing:          "Analysing stocks…",
};

const ScanDetailPanel = memo(function ScanDetailPanel({
  progress,
  streamingSignals,
  scanStartedAt,
  onStop,
  isStopping,
  buyCount,
  watchCount,
  noActCount,
  phaseMessage,
}: {
  progress: { done: number; total: number };
  streamingSignals: StreamingSignal[];
  scanStartedAt: number | null;
  onStop: () => void;
  isStopping: boolean;
  buyCount: number;
  watchCount: number;
  noActCount: number;
  phaseMessage: string | null;
}) {
  const elapsed  = useElapsedSeconds(scanStartedAt);
  const hasReal  = progress.total > 0;
  const pct      = hasReal ? Math.min(100, Math.round((progress.done / progress.total) * 100)) : 0;
  const rate     = elapsed > 2 ? progress.done / elapsed : 0;
  const etaSec   = rate > 0 ? Math.round((progress.total - progress.done) / rate) : null;

  // Last 10 signals in reverse order (newest first)
  const recentFeed = useMemo(
    () => [...streamingSignals].slice(-10).reverse(),
    [streamingSignals],
  );

  return (
    <Card sx={{ mb: 2, bgcolor: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.25)" }}>
      <CardContent sx={{ py: 2, "&:last-child": { pb: 2 } }}>

        {/* ── Header ────────────────────────────────────────────────────── */}
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={1.5}>
          <Box display="flex" alignItems="center" gap={1}>
            <CircularProgress size={16} thickness={5} sx={{ color: STATUS_COLORS.SWING }} />
            <Typography variant="subtitle2" fontWeight={700}>GATE Scan Running</Typography>
          </Box>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Typography variant="caption" color="text.secondary">
              ⏱ {formatDuration(elapsed)}
            </Typography>
            {etaSec !== null && etaSec > 5 && (
              <Typography variant="caption" color="text.disabled">
                ETA ~{formatDuration(etaSec)}
              </Typography>
            )}
            <Button
              size="small"
              variant="outlined"
              color="error"
              disabled={isStopping}
              onClick={onStop}
              aria-label="Stop current scan"
              startIcon={isStopping ? <CircularProgress size={12} color="inherit" /> : undefined}
              sx={{ fontSize: "0.72rem", py: 0.3, minWidth: 88 }}
            >
              {isStopping ? "Stopping…" : "Stop Scan"}
            </Button>
          </Stack>
        </Box>

        {/* ── Progress bar ──────────────────────────────────────────────── */}
        <Box mb={1.5}>
          <Box display="flex" justifyContent="space-between" alignItems="baseline" mb={0.5}>
            <Typography variant="caption" color="text.secondary">
              {hasReal
                ? `${progress.done.toLocaleString()} / ${progress.total.toLocaleString()} symbols`
                : (phaseMessage ?? "Initialising…")}
            </Typography>
            {hasReal && (
              <Typography variant="caption" fontWeight={700} color="primary.light">
                {pct}%
              </Typography>
            )}
          </Box>
          <LinearProgress
            variant={hasReal ? "determinate" : "indeterminate"}
            value={hasReal ? pct : undefined}
            sx={{ height: 6, borderRadius: 3 }}
          />
          {elapsed > SLOW_SCAN_THRESHOLD_SEC && (
            <Typography variant="caption" color="warning.main" display="block" mt={0.6}>
              Scanning the full master list is taking longer than usual — results
              will still appear automatically. You can Stop the scan if needed.
            </Typography>
          )}
        </Box>

        {/* ── Signal counters ───────────────────────────────────────────── */}
        <Grid container spacing={1.5} mb={recentFeed.length > 0 ? 1.5 : 0}>
          {[
            { label: "BUY Signals", count: buyCount,   color: STATUS_COLORS.INVESTMENT, Icon: TrendingUp      },
            { label: "Watch",       count: watchCount,  color: STATUS_COLORS.WATCH,      Icon: Visibility      },
            { label: "No Action",   count: noActCount,  color: STATUS_COLORS.IGNORE,     Icon: DoNotDisturbAlt },
          ].map(({ label, count, color, Icon }) => (
            <Grid item xs={4} key={label}>
              <Box
                display="flex" alignItems="center" gap={1}
                sx={{ py: 1, px: 1.5, bgcolor: `${color}0d`, borderRadius: 1.5, border: `1px solid ${color}25` }}
              >
                <Icon sx={{ fontSize: 18, color, flexShrink: 0 }} />
                <Box>
                  <Typography variant="h6" fontWeight={700} color={color} lineHeight={1.1}>
                    {count}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.65rem" }}>
                    {label}
                  </Typography>
                </Box>
              </Box>
            </Grid>
          ))}
        </Grid>

        {/* ── Recent signals feed ───────────────────────────────────────── */}
        {recentFeed.length > 0 && (
          <>
            <Divider sx={{ borderColor: "rgba(255,255,255,0.06)", mb: 1 }} />
            <Typography variant="caption" color="text.disabled" display="block" mb={0.6}>
              Recent signals
            </Typography>
            <Stack spacing={0.35}>
              {recentFeed.map((sig, i) => {
                const isBuy = BUY_CATEGORIES.has(sig.category);
                const col   = isBuy ? STATUS_COLORS.INVESTMENT : sig.category === "WATCH" ? STATUS_COLORS.WATCH : STATUS_COLORS.IGNORE;
                const meta  = CATEGORY_DISPLAY[sig.category as SignalCategory];
                return (
                  <Box
                    key={`${sig.symbol}-${i}`}
                    display="flex" alignItems="center" gap={1.5}
                    sx={i === 0 ? FEED_ROW_FIRST_SX : FEED_ROW_BASE_SX}
                  >
                    <StockLink symbol={sig.symbol} variant="caption" fontWeight={700} sx={{ minWidth: 80 }} />
                    <Chip
                      label={meta?.label ?? sig.category}
                      size="small"
                      sx={{ height: 17, fontSize: "0.6rem", fontWeight: 600,
                        bgcolor: `${col}18`, color: col, border: `1px solid ${col}40` }}
                    />
                    {sig.gate_strength != null && (
                      <Typography variant="caption" color="text.secondary">
                        GATE {sig.gate_strength.toFixed(0)}
                      </Typography>
                    )}
                    {sig.entry != null && (
                      <Typography variant="caption" color="text.disabled" ml="auto">
                        {formatPrice(sig.entry)}
                      </Typography>
                    )}
                    {sig.rr_t1 != null && (
                      <Typography
                        variant="caption"
                        fontWeight={600}
                        color={sig.rr_t1 >= 2 ? "success.main" : "text.secondary"}
                        sx={{ minWidth: 36, textAlign: "right" }}
                      >
                        {sig.rr_t1.toFixed(1)}x
                      </Typography>
                    )}
                  </Box>
                );
              })}
            </Stack>
          </>
        )}
      </CardContent>
    </Card>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Scan completion summary card
// ─────────────────────────────────────────────────────────────────────────────

const ScanCompletionCard = memo(function ScanCompletionCard({ summary }: { summary: CompletionSummary }) {
  return (
    <Card sx={{ mb: 2, bgcolor: "rgba(34,197,94,0.05)", border: "1px solid rgba(34,197,94,0.2)" }}>
      <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Box display="flex" alignItems="center" gap={1} mb={1}>
          <CheckCircleOutline sx={{ fontSize: 16, color: "success.main" }} />
          <Typography variant="body2" fontWeight={600}>
            Scan complete — {summary.signals_count.toLocaleString()} signals in{" "}
            {formatDuration(summary.duration_sec)}
          </Typography>
        </Box>
        <Stack direction="row" spacing={3}>
          <Box>
            <Typography variant="body2" fontWeight={700} color={STATUS_COLORS.INVESTMENT}>{summary.buy_count}</Typography>
            <Typography variant="caption" color="text.secondary">BUY Signals</Typography>
          </Box>
          <Box>
            <Typography variant="body2" fontWeight={700} color={STATUS_COLORS.WATCH}>{summary.watch_count}</Typography>
            <Typography variant="caption" color="text.secondary">Watch</Typography>
          </Box>
          <Box>
            <Typography variant="body2" fontWeight={700} color={STATUS_COLORS.IGNORE}>{summary.no_action_count}</Typography>
            <Typography variant="caption" color="text.secondary">No Action</Typography>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Main scanner page
// ─────────────────────────────────────────────────────────────────────────────

export default function ScannerPage() {
  const dispatch = useDispatch<AppDispatch>();

  const scanProgress          = useSelector(selectScanProgress);
  const scanStartedAt         = useSelector(selectScanStartedAt);
  const lastCompletionSummary = useSelector(selectCompletionSummary);
  const currentScanId         = useSelector(selectCurrentScanId);
  const streamingRaw          = useSelector(selectStreamingSignals);
  const streamingBuyCount     = useSelector(selectStreamingBuyCount);
  const streamingWatchCount   = useSelector(selectStreamingWatchCount);
  const streamingNoActCount   = useSelector(selectStreamingNoActCount);
  const scanPhaseMessage      = useSelector(selectScanPhaseMessage);

  const [mainTab, setMainTab]       = useState(0);   // 0 = Signals, 1 = Paper Trading, 2 = Backtest
  const [activeTab, setActiveTab]   = useState<FilterTab>("ALL");
  const [page, setPage]             = useState(1);

  // Paper Trading open positions count for badge
  const { data: openPositions } = useGetPositionsQuery();
  const openPositionsCount = openPositions?.length ?? 0;

  const isScanning = !!scanProgress;

  // Master Stock List size (for the read-only universe label)
  const { data: stockStats } = useGetStockStatsQuery();
  const masterCount = stockStats?.total ?? null;

  // ── Scan control ───────────────────────────────────────────────────────
  const [triggerScan, { isLoading: isTriggerLoading }] = useTriggerScanMutation();
  const [stopScan,    { isLoading: isStopping       }] = useStopScanMutation();

  // ── Detect already-running scans on page load ──────────────────────────
  const { data: scans } = useListScansQuery();
  const latestScan = scans?.[0];

  // Use a ref so the effect only re-runs when `scans` changes, not when
  // isScanning changes. Without this, dispatching scanStarted() inside the
  // effect flips isScanning → true → dependency changed → effect re-runs →
  // finds the same pending scan → dispatches again → infinite loop.
  const isScanningRef = useRef(false);
  isScanningRef.current = isScanning;

  useEffect(() => {
    if (!scans) return;
    if (isScanningRef.current) return;
    const runningScan = scans.find(
      (s) => s.status === "pending" || s.status === "running"
    );
    if (runningScan) {
      dispatch(scanStarted(runningScan.id));
    }
  }, [scans, dispatch]);

  const handleStopScan = useCallback(async () => {
    const id = currentScanId ?? scans?.find(s => s.status === "pending" || s.status === "running")?.id;
    if (!id) return;
    try {
      await stopScan(id).unwrap();
      dispatch(scanFailed());
    } catch (err: any) {
      if (err?.status === 409) {
        dispatch(scanFailed());
      }
    }
  }, [currentScanId, scans, stopScan, dispatch]);

  const handleRunScan = useCallback(async () => {
    // Clear previous results immediately so the table is blank before the API
    // call even returns — no flash of stale data while the request is in-flight.
    dispatch(scanStarted(undefined));
    try {
      const { scan_id } = await triggerScan({ mode: SCAN_MODE }).unwrap();
      dispatch(scanStarted(scan_id));
    } catch (err: any) {
      if (err?.status === 409) {
        const runningScan = scans?.find(
          (s) => s.status === "pending" || s.status === "running"
        );
        if (runningScan) {
          dispatch(scanStarted(runningScan.id));
        } else {
          dispatch(scanStarted(undefined));
        }
      } else {
        console.error("Scan failed to start", err);
        dispatch(scanFailed());
      }
    }
  }, [triggerScan, scans, dispatch]);

  // ── Completion-detection fallback (fixes "infinite scanning" on mobile) ──
  // The WebSocket scan.complete/scan.failed event can be missed when a mobile
  // browser backgrounds the tab and the socket reconnects (missed events are
  // not replayed). We poll the scan status as a safety net so the UI always
  // exits the scanning state once the backend finishes.
  const activeScanId =
    currentScanId ??
    scans?.find((s) => s.status === "pending" || s.status === "running")?.id ??
    null;

  const { data: polledScan } = useGetScanStatusQuery(activeScanId as string, {
    skip: !isScanning || !activeScanId,
    pollingInterval: 5000,
    refetchOnReconnect: true,
    refetchOnFocus: true,
  });

  useEffect(() => {
    if (!isScanning || !polledScan) return;
    if (polledScan.status === "done") {
      dispatch(scanCompleted({
        scan_id:       polledScan.id,
        signals_count: polledScan.signals_found ?? 0,
      }));
      dispatch(scannerApi.util.invalidateTags(["Signal", "Scan", "Dashboard"]));
    } else if (polledScan.status === "failed") {
      dispatch(scanFailed());
    }
  }, [isScanning, polledScan, dispatch]);

  // When the tab returns to the foreground mid-scan, immediately re-sync the
  // scan list + results instead of waiting for the next poll tick.
  useEffect(() => {
    if (!isScanning) return;
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        dispatch(scannerApi.util.invalidateTags(["Scan", "Signal"]));
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [isScanning, dispatch]);

  // ── Fetched signals (post-scan, paginated) ─────────────────────────────
  // Signals are always daily (signal_timeframe="1d") — no TF filter needed.
  const statusFilter = activeTab === "ALL" ? undefined : activeTab;
  const { data: fetchedData, isFetching, isError: signalsError, refetch: refetchSignals } = useGetScanResultsQuery(
    {
      status:  statusFilter,
      limit:   PAGE_SIZE,
      offset:  (page - 1) * PAGE_SIZE,
    },
    { skip: isScanning }
  );

  // ── Per-status counts for tab badges (post-scan) ───────────────────────
  const { data: signalCounts } = useGetSignalCountsQuery(undefined, {
    skip: isScanning,
  });

  // ── Streaming signals (during scan) ───────────────────────────────────
  const streamingSignals: Signal[] = useMemo(
    () => streamingRaw.map(streamingToSignal),
    [streamingRaw]
  );

  const filteredStreaming = useMemo(
    () => filterByTab(streamingSignals, activeTab),
    [streamingSignals, activeTab]
  );

  const streamingCounts = useMemo(
    () => countByStatus(streamingSignals),
    [streamingSignals]
  );

  // ── Decide what to show ────────────────────────────────────────────────
  const displaySignals = isScanning ? filteredStreaming : (fetchedData?.items ?? []);
  const totalSignals   = isScanning ? filteredStreaming.length : (fetchedData?.total ?? 0);
  const totalPages     = Math.max(1, Math.ceil(totalSignals / PAGE_SIZE));

  // ── Tab counts (for badges) ────────────────────────────────────────────
  // During streaming: count from streaming signals
  // After scan: use the dedicated counts endpoint for all tabs
  const tabCount = (tab: FilterTab): number | null => {
    if (isScanning) {
      if (tab === "ALL") return streamingSignals.length;
      return streamingCounts[tab as DisplayStatus] ?? 0;
    }
    if (!signalCounts) return null;
    switch (tab) {
      case "ALL":       return signalCounts.total;
      case "BUY":       return signalCounts.buy_count;
      case "WATCH":     return signalCounts.watch_count;
      case "NO_ACTION": return signalCounts.no_action_count;
      default:          return null;
    }
  };

  return (
    <Box>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <Box display="flex" alignItems="center" gap={2} mb={1.5} flexWrap="wrap">
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6" fontWeight={700} lineHeight={1.2}>
            GATE Scanner
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Daily timeframe strategy · signals generated on 1D bars · SL from 4H EMA200 · HTF confirmation from 1W
          </Typography>
        </Box>

        <Tooltip title="Scans the complete Master Stock List — no Nifty 50 / 500 / F&O filtering">
          <Chip
            label={
              masterCount != null
                ? `Master List · ${masterCount.toLocaleString()} stocks`
                : "Master Stock List"
            }
            size="small"
            variant="outlined"
            sx={{ fontWeight: 600, fontSize: "0.72rem", borderColor: "rgba(255,255,255,0.18)" }}
          />
        </Tooltip>

        {mainTab === 0 && (
          <Button
            variant="contained"
            size="small"
            startIcon={
              isTriggerLoading
                ? <CircularProgress size={14} color="inherit" />
                : <PlayArrow />
            }
            onClick={handleRunScan}
            disabled={isTriggerLoading || isScanning}
            sx={{ minWidth: 110 }}
          >
            {isTriggerLoading ? "Starting…" : "Run Scan"}
          </Button>
        )}
      </Box>

      {/* ── Main section tabs: Signals | Paper Trading | Backtest ── */}
      <Box sx={{ borderBottom: "1px solid rgba(255,255,255,0.08)", mb: 2 }}>
        <Tabs
          value={mainTab}
          onChange={(_, v) => setMainTab(v)}
          variant="scrollable"
          scrollButtons="auto"
          allowScrollButtonsMobile
          sx={{
            minHeight: 40,
            "& .MuiTab-root": { minHeight: 40, fontSize: "0.82rem", px: { xs: 1.5, sm: 2 } },
            "& .MuiTabs-scrollButtons": { color: "text.secondary" },
          }}
        >
          <Tab label="Signals" />
          <Tab
            label={
              <Box display="flex" alignItems="center" gap={0.7}>
                <TrendingUp sx={{ fontSize: 14 }} />
                <span>Paper Trading</span>
                {openPositionsCount > 0 && (
                  <Chip
                    label={openPositionsCount}
                    size="small"
                    sx={{
                      height: 17,
                      fontSize: "0.62rem",
                      bgcolor: mainTab === 1 ? "rgba(34,197,94,0.25)" : "rgba(255,255,255,0.06)",
                      color: mainTab === 1 ? "success.main" : "text.secondary",
                      fontWeight: 600,
                    }}
                  />
                )}
              </Box>
            }
          />
          <Tab
            label={
              <Box display="flex" alignItems="center" gap={0.7}>
                <BarChart sx={{ fontSize: 14 }} />
                <span>Backtest</span>
              </Box>
            }
          />
        </Tabs>
      </Box>

      {/* ── Signals tab ─────────────────────────────────────────────────── */}
      {mainTab === 0 && (
        <>
          {/* Scan meta */}
          {latestScan && !isScanning && (
            <Box display="flex" alignItems="center" gap={0.5} mb={2}>
              <Schedule sx={{ fontSize: 13, color: "text.disabled" }} />
              <Typography variant="caption" color="text.secondary">
                Last scan: {formatIST(latestScan.triggered_at)}
                {latestScan.universe_size != null && latestScan.universe_size > 0 &&
                  ` · ${latestScan.universe_size.toLocaleString()} stocks scanned`}
                {latestScan.signals_found != null && ` · ${latestScan.signals_found.toLocaleString()} signals found`}
              </Typography>
            </Box>
          )}

          {/* Scan detail panel (running) / completion card (just finished) */}
          {scanProgress && (
            <ScanDetailPanel
              progress={scanProgress}
              streamingSignals={streamingRaw}
              scanStartedAt={scanStartedAt}
              onStop={handleStopScan}
              isStopping={isStopping}
              buyCount={streamingBuyCount}
              watchCount={streamingWatchCount}
              noActCount={streamingNoActCount}
              phaseMessage={scanPhaseMessage}
            />
          )}
          {!scanProgress && lastCompletionSummary && (
            <ScanCompletionCard summary={lastCompletionSummary} />
          )}

          {/* Signal filter tabs + table */}
          <Card sx={{ mb: 0 }}>
            <Box
              sx={{
                borderBottom: "1px solid rgba(255,255,255,0.06)",
                display: "flex",
                alignItems: "center",
                px: 1,
              }}
            >
              <Tabs
                value={activeTab}
                onChange={(_, v) => { setActiveTab(v); setPage(1); }}
                variant="scrollable"
                scrollButtons="auto"
                allowScrollButtonsMobile
                sx={{
                  flex: 1,
                  minHeight: 42,
                  "& .MuiTab-root": { minHeight: 42, fontSize: "0.78rem", px: { xs: 1, sm: 1.5 } },
                  "& .MuiTabs-scrollButtons": { color: "text.secondary" },
                }}
              >
                {TABS.map(({ value, label, color }) => {
                  const count = tabCount(value);
                  return (
                    <Tab
                      key={value}
                      value={value}
                      label={
                        <Box display="flex" alignItems="center" gap={0.6}>
                          <span>{label}</span>
                          {count != null && (
                            <Chip
                              label={count}
                              size="small"
                              sx={tabChipSx(color, activeTab === value)}
                            />
                          )}
                        </Box>
                      }
                    />
                  );
                })}
              </Tabs>
            </Box>

            {signalsError && !isScanning && (
              <PageError
                message="Could not load scan results"
                detail="Ensure the API is reachable and a scan has been run"
                onRetry={refetchSignals}
              />
            )}

            {!signalsError && displaySignals.length === 0 && !isFetching ? (
              isScanning ? (
                <EmptyState
                  title="Scan in progress — no signals yet"
                  description={
                    activeTab === "ALL"
                      ? "Results will appear here as each batch of stocks completes"
                      : `No ${activeTab === "BUY" ? "BUY" : activeTab === "WATCH" ? "Watch" : "No Action"} signals found yet — switch to the ALL tab to see everything streaming in`
                  }
                />
              ) : (
                <EmptyState
                  title={
                    activeTab === "BUY"
                      ? "No BUY opportunities in the latest scan"
                      : activeTab === "WATCH"
                      ? "No stocks in Watch status"
                      : latestScan
                      ? "No signals match the selected filter"
                      : "No scan has been run yet"
                  }
                  description={
                    !latestScan
                      ? "Click Run Scan to scan the full Master Stock List"
                      : "Try a different filter or run a new scan"
                  }
                />
              )
            ) : !signalsError ? (
              <SignalTable
                signals={displaySignals}
                loading={isFetching && !isScanning}
              />
            ) : null}

            {!isScanning && totalPages > 1 && (
              <Box display="flex" justifyContent="center" py={1.5} borderTop="1px solid rgba(255,255,255,0.06)">
                <Pagination
                  count={totalPages}
                  page={page}
                  onChange={(_, p) => setPage(p)}
                  size="small"
                  color="primary"
                />
              </Box>
            )}
          </Card>

          {isScanning && streamingRaw.length > 0 && (
            <Box mt={1} px={0.5}>
              <Typography variant="caption" color="text.disabled">
                Table shows {filteredStreaming.length} of {streamingRaw.length} signals matching current filter — results finalise when scan completes
              </Typography>
            </Box>
          )}
        </>
      )}

      {/* ── Paper Trading tab ─────────────────────────────────────────────── */}
      {mainTab === 1 && <PaperTradingPanel />}

      {/* ── Backtest tab ──────────────────────────────────────────────────── */}
      {mainTab === 2 && <BacktestPanel />}
    </Box>
  );
}
