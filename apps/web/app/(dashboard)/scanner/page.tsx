"use client";
import { useState, useMemo, useEffect } from "react";
import {
  Box, Card, CardContent, Typography, Chip, Tab, Tabs,
  LinearProgress, CircularProgress, Select, MenuItem,
  FormControl, InputLabel, Stack, Pagination,
  Button, Tooltip,
} from "@mui/material";
import { PlayArrow, Schedule, FilterList } from "@mui/icons-material";
import { useSelector, useDispatch } from "react-redux";
import { SignalTable, CATEGORY_DISPLAY } from "@/components/domain/SignalTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageError } from "@/components/ui/PageError";
import {
  useGetScanResultsQuery,
  useListScansQuery,
  useTriggerScanMutation,
} from "@/store/api/scannerApi";
import { scannerApi } from "@/store/api/scannerApi";
import { stockMasterApi } from "@/store/api/stockMasterApi";
import { scanStarted, scanCompleted, scanFailed, clearStreamingSignals } from "@/store/slices/wsSlice";
import { formatIST } from "@/lib/formatters";
import type { RootState, AppDispatch } from "@/store";
import type { Signal, SignalCategory, DisplayStatus } from "@/types/signal";
import type { StreamingSignal } from "@/types/scan";

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
// Scan progress banner
// ─────────────────────────────────────────────────────────────────────────────

function ScanProgressBanner({
  progress,
  streamingCount,
}: {
  progress: { done: number; total: number } | null;
  streamingCount: number;
}) {
  if (!progress) return null;
  const hasReal = progress.total > 0;
  const pct = hasReal ? Math.min(100, Math.round((progress.done / progress.total) * 100)) : 0;

  return (
    <Card sx={{ mb: 2, bgcolor: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)" }}>
      <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.8}>
          <Box display="flex" alignItems="center" gap={1}>
            <CircularProgress size={14} thickness={5} />
            <Typography variant="body2" fontWeight={600}>
              Scanning in progress…
            </Typography>
          </Box>
          <Box display="flex" alignItems="center" gap={2}>
            {hasReal && (
              <Typography variant="caption" color="text.secondary">
                {progress.done} / {progress.total} stocks ({pct}%)
              </Typography>
            )}
            {streamingCount > 0 && (
              <Chip
                label={`${streamingCount} signals found`}
                size="small"
                color="success"
                sx={{ fontSize: "0.68rem", height: 20 }}
              />
            )}
          </Box>
        </Box>
        <LinearProgress
          variant={hasReal ? "determinate" : "indeterminate"}
          value={hasReal ? pct : undefined}
          sx={{ height: 5, borderRadius: 2 }}
        />
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main scanner page
// ─────────────────────────────────────────────────────────────────────────────

export default function ScannerPage() {
  const dispatch = useDispatch<AppDispatch>();

  const scanProgress    = useSelector((s: RootState) => s.ws.scanProgress);
  const currentScanId   = useSelector((s: RootState) => s.ws.currentScanId);
  const streamingRaw    = useSelector((s: RootState) => s.ws.streamingSignals);

  const [activeTab, setActiveTab]   = useState<FilterTab>("BUY");
  const [scanMode, setScanMode]     = useState("nifty500");
  const [page, setPage]             = useState(1);

  const isScanning = !!scanProgress;

  // ── Scan control ───────────────────────────────────────────────────────
  const [triggerScan, { isLoading: isTriggerLoading }] = useTriggerScanMutation();

  // ── Detect already-running scans on page load ──────────────────────────
  const { data: scans } = useListScansQuery();
  const latestScan = scans?.[0];

  useEffect(() => {
    if (!scans || isScanning) return;
    const runningScan = scans.find(
      (s) => s.status === "pending" || s.status === "running"
    );
    if (runningScan) {
      dispatch(scanStarted(runningScan.id));
    }
  }, [scans, isScanning, dispatch]);

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

      {/* ── Progress banner ──────────────────────────────────────────────── */}
      <ScanProgressBanner progress={scanProgress} streamingCount={streamingRaw.length} />

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

      {/* ── Streaming info footer ─────────────────────────────────────────── */}
      {isScanning && streamingRaw.length > 0 && (
        <Box mt={1} px={0.5}>
          <Typography variant="caption" color="text.disabled">
            Showing {filteredStreaming.length} of {streamingRaw.length} signals found so far —
            results will refresh when scan completes
          </Typography>
        </Box>
      )}
    </Box>
  );
}
