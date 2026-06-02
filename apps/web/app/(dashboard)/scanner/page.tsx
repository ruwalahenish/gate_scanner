"use client";
import { useState, useMemo, useEffect, useRef } from "react";
import {
  Box, Card, CardContent, Grid, Typography, Chip, Tab, Tabs,
  LinearProgress, CircularProgress, Select, MenuItem,
  FormControl, InputLabel, Stack, Pagination,
  Button, Divider,
} from "@mui/material";
import {
  PlayArrow, Schedule, CheckCircleOutline,
  TrendingUp, Visibility, DoNotDisturbAlt,
} from "@mui/icons-material";
import { useSelector, useDispatch } from "react-redux";
import { SignalTable, CATEGORY_DISPLAY } from "@/components/domain/SignalTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageError } from "@/components/ui/PageError";
import {
  useGetScanResultsQuery,
  useListScansQuery,
  useTriggerScanMutation,
  useStopScanMutation,
} from "@/store/api/scannerApi";
import { scannerApi } from "@/store/api/scannerApi";
import { stockMasterApi } from "@/store/api/stockMasterApi";
import { scanStarted, scanFailed, clearStreamingSignals } from "@/store/slices/wsSlice";
import { formatIST } from "@/lib/formatters";
import type { RootState, AppDispatch } from "@/store";
import type { Signal, SignalCategory, DisplayStatus } from "@/types/signal";
import type { StreamingSignal } from "@/types/scan";
import type { CompletionSummary } from "@/store/slices/wsSlice";

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 50;

const SCAN_MODES = [
  { value: "nifty50",  label: "Nifty 50"  },
  { value: "nifty500", label: "Nifty 500" },
  { value: "fno",      label: "F&O"       },
  { value: "daily",    label: "Default"   },
] as const;

type FilterTab = "ALL" | "BUY" | "WATCH" | "NO_ACTION";

const TABS: { value: FilterTab; label: string; color: string }[] = [
  { value: "ALL",       label: "All",              color: "#94a3b8" },
  { value: "BUY",       label: "BUY Opportunity",  color: "#22c55e" },
  { value: "WATCH",     label: "Watch",            color: "#f59e0b" },
  { value: "NO_ACTION", label: "No Action",        color: "#64748b" },
];

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

const BUY_CATS = new Set(["INVESTMENT", "SWING", "POSITIONAL"]);

// ─────────────────────────────────────────────────────────────────────────────
// Rich scan detail panel (replaces thin banner)
// ─────────────────────────────────────────────────────────────────────────────

function ScanDetailPanel({
  progress,
  streamingSignals,
  scanStartedAt,
  onStop,
  isStopping,
}: {
  progress: { done: number; total: number };
  streamingSignals: StreamingSignal[];
  scanStartedAt: number | null;
  onStop: () => void;
  isStopping: boolean;
}) {
  const elapsed  = useElapsedSeconds(scanStartedAt);
  const hasReal  = progress.total > 0;
  const pct      = hasReal ? Math.min(100, Math.round((progress.done / progress.total) * 100)) : 0;
  const rate     = elapsed > 2 ? progress.done / elapsed : 0;
  const etaSec   = rate > 0 ? Math.round((progress.total - progress.done) / rate) : null;

  const buyCount      = streamingSignals.filter(s => BUY_CATS.has(s.category)).length;
  const watchCount    = streamingSignals.filter(s => s.category === "WATCH").length;
  const noActCount    = streamingSignals.filter(s => s.category === "IGNORE").length;

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
            <CircularProgress size={16} thickness={5} sx={{ color: "#6366f1" }} />
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
                : "Initialising…"}
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
        </Box>

        {/* ── Signal counters ───────────────────────────────────────────── */}
        <Grid container spacing={1.5} mb={recentFeed.length > 0 ? 1.5 : 0}>
          {[
            { label: "BUY Signals",   count: buyCount,   color: "#22c55e", Icon: TrendingUp       },
            { label: "Watch",          count: watchCount,  color: "#f59e0b", Icon: Visibility       },
            { label: "No Action",      count: noActCount,  color: "#64748b", Icon: DoNotDisturbAlt  },
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
                const isBuy = BUY_CATS.has(sig.category);
                const col   = isBuy ? "#22c55e" : sig.category === "WATCH" ? "#f59e0b" : "#64748b";
                const meta  = CATEGORY_DISPLAY[sig.category as SignalCategory];
                return (
                  <Box
                    key={`${sig.symbol}-${i}`}
                    display="flex" alignItems="center" gap={1.5}
                    sx={{ py: 0.4, px: 0.8, borderRadius: 1, bgcolor: "rgba(255,255,255,0.02)",
                      "&:first-of-type": { bgcolor: "rgba(99,102,241,0.08)" } }}
                  >
                    <Typography variant="caption" fontWeight={700} sx={{ minWidth: 80 }}>
                      {sig.symbol}
                    </Typography>
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
                        ₹{sig.entry.toLocaleString("en-IN")}
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
}

// ─────────────────────────────────────────────────────────────────────────────
// Scan completion summary card
// ─────────────────────────────────────────────────────────────────────────────

function ScanCompletionCard({ summary }: { summary: CompletionSummary }) {
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
            <Typography variant="body2" fontWeight={700} color="#22c55e">{summary.buy_count}</Typography>
            <Typography variant="caption" color="text.secondary">BUY Signals</Typography>
          </Box>
          <Box>
            <Typography variant="body2" fontWeight={700} color="#f59e0b">{summary.watch_count}</Typography>
            <Typography variant="caption" color="text.secondary">Watch</Typography>
          </Box>
          <Box>
            <Typography variant="body2" fontWeight={700} color="#64748b">{summary.no_action_count}</Typography>
            <Typography variant="caption" color="text.secondary">No Action</Typography>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main scanner page
// ─────────────────────────────────────────────────────────────────────────────

export default function ScannerPage() {
  const dispatch = useDispatch<AppDispatch>();

  const scanProgress          = useSelector((s: RootState) => s.ws.scanProgress);
  const scanStartedAt         = useSelector((s: RootState) => s.ws.scanStartedAt);
  const lastCompletionSummary = useSelector((s: RootState) => s.ws.lastCompletionSummary);
  const currentScanId         = useSelector((s: RootState) => s.ws.currentScanId);
  const streamingRaw          = useSelector((s: RootState) => s.ws.streamingSignals);

  const [activeTab, setActiveTab]   = useState<FilterTab>("BUY");
  const [scanMode, setScanMode]     = useState("nifty500");
  const [page, setPage]             = useState(1);

  const isScanning = !!scanProgress;

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

  const handleStopScan = async () => {
    const id = currentScanId ?? scans?.find(s => s.status === "pending" || s.status === "running")?.id;
    if (!id) return;
    try {
      await stopScan(id).unwrap();
      dispatch(scanFailed());              // reset UI immediately without waiting for WS round-trip
    } catch (err: any) {
      if (err?.status === 409) {
        dispatch(scanFailed());            // scan already finished — just clear local state
      }
    }
  };

  const handleRunScan = async () => {
    try {
      const { scan_id } = await triggerScan({ mode: scanMode }).unwrap();
      dispatch(scanStarted(scan_id));
    } catch (err: any) {
      // 409 = scan already in progress — sync UI state
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
      }
    }
  };

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
  // After scan: shown from API totals (approximated)
  const tabCount = (tab: FilterTab): number | null => {
    if (!isScanning && !fetchedData) return null;
    if (isScanning) {
      if (tab === "ALL") return streamingSignals.length;
      return streamingCounts[tab as DisplayStatus] ?? 0;
    }
    // Post-scan: only current tab count is precise; others shown as "—"
    if (tab === "ALL") return fetchedData?.total ?? null;
    if (tab === activeTab) return fetchedData?.total ?? null;
    return null;
  };

  return (
    <Box>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <Box display="flex" alignItems="center" gap={2} mb={0.5} flexWrap="wrap">
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6" fontWeight={700} lineHeight={1.2}>
            GATE Scanner
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Daily timeframe strategy · signals generated on 1D bars · SL from 4H EMA200 · HTF confirmation from 1W
          </Typography>
        </Box>

        {/* Mode selector */}
        <FormControl size="small" sx={{ minWidth: 130 }}>
          <InputLabel id="scan-mode-label" sx={{ fontSize: "0.8rem" }}>Universe</InputLabel>
          <Select
            labelId="scan-mode-label"
            value={scanMode}
            label="Universe"
            onChange={(e) => setScanMode(e.target.value)}
            disabled={isScanning}
            sx={{ fontSize: "0.82rem" }}
          >
            {SCAN_MODES.map((m) => (
              <MenuItem key={m.value} value={m.value} sx={{ fontSize: "0.82rem" }}>
                {m.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Run Scan button */}
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
      </Box>

      {/* ── Scan meta ───────────────────────────────────────────────────── */}
      {latestScan && !isScanning && (
        <Box display="flex" alignItems="center" gap={0.5} mb={2}>
          <Schedule sx={{ fontSize: 13, color: "text.disabled" }} />
          <Typography variant="caption" color="text.secondary">
            Last scan: {formatIST(latestScan.triggered_at)}
            {latestScan.universe_size != null && ` · ${latestScan.universe_size.toLocaleString()} stocks scanned`}
            {latestScan.signals_found != null && ` · ${latestScan.signals_found} daily setups found`}
          </Typography>
        </Box>
      )}

      {/* ── Scan detail panel (running) / completion card (just finished) ── */}
      {scanProgress && (
        <ScanDetailPanel
          progress={scanProgress}
          streamingSignals={streamingRaw}
          scanStartedAt={scanStartedAt}
          onStop={handleStopScan}
          isStopping={isStopping}
        />
      )}
      {!scanProgress && lastCompletionSummary && (
        <ScanCompletionCard summary={lastCompletionSummary} />
      )}

      {/* ── Filter tabs ──────────────────────────────────────────────────── */}
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
            sx={{
              flex: 1,
              minHeight: 42,
              "& .MuiTab-root": { minHeight: 42, fontSize: "0.78rem", px: 1.5 },
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
                          sx={{
                            height: 17,
                            fontSize: "0.62rem",
                            bgcolor: activeTab === value ? `${color}30` : "rgba(255,255,255,0.06)",
                            color: activeTab === value ? color : "text.secondary",
                            fontWeight: 600,
                          }}
                        />
                      )}
                    </Box>
                  }
                />
              );
            })}
          </Tabs>
        </Box>

        {/* ── Error state ──────────────────────────────────────────────────── */}
        {signalsError && !isScanning && (
          <PageError
            message="Could not load scan results"
            detail="Ensure the API is reachable and a scan has been run"
            onRetry={refetchSignals}
          />
        )}

        {/* ── Column headers + signal rows ────────────────────────────────── */}
        {!signalsError && displaySignals.length === 0 && !isFetching && !isScanning ? (
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
                ? "Select a universe and click Run Scan to start"
                : "Try a different filter or run a new scan"
            }
          />
        ) : !signalsError ? (
          <SignalTable
            signals={displaySignals}
            loading={isFetching && !isScanning}
          />
        ) : null}

        {/* ── Pagination (post-scan only) ──────────────────────────────────── */}
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

      {/* ── Footer note (scanning) ─────────────────────────────────────────── */}
      {isScanning && streamingRaw.length > 0 && (
        <Box mt={1} px={0.5}>
          <Typography variant="caption" color="text.disabled">
            Table shows {filteredStreaming.length} of {streamingRaw.length} signals matching current filter — results finalise when scan completes
          </Typography>
        </Box>
      )}
    </Box>
  );
}
