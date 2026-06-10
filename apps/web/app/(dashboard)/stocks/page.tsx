"use client";
import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Box, Typography, Grid, Card, CardContent, Chip, Button, TextField,
  Select, MenuItem, FormControl, InputLabel, Stack, Tooltip,
  CircularProgress, Alert, LinearProgress,
  Dialog, DialogTitle, DialogContent, DialogActions, Stepper, Step, StepLabel,
} from "@mui/material";
import { DataGrid, type GridColDef, type GridPaginationModel, type GridRowParams } from "@mui/x-data-grid";
import { Sync, CheckCircle, Schedule, ErrorOutline, Info } from "@mui/icons-material";
import { useSnackbar } from "notistack";
import { useSelector, useDispatch } from "react-redux";
import { StatCard } from "@/components/ui/StatCard";
import { GATEBar } from "@/components/ui/GATEBar";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { formatCompact, formatPrice, formatIST, formatRR } from "@/lib/formatters";
import { STATUS_COLORS, GATE_COLOR } from "@/lib/constants";
import {
  useListStocksQuery,
  useGetStockStatsQuery,
  useTriggerSyncMutation,
  useGetSyncStatusQuery,
  stockMasterApi,
} from "@/store/api/stockMasterApi";
import {
  selectScanProgress,
  selectIsScanning,
  selectHasRealProgress,
  selectScanProgressPct,
  selectStreamingCount,
} from "@/store/selectors";
import type { AppDispatch } from "@/store";
import type { StockFilters, Stock, SyncTaskStatus } from "@/types/stock";
import type { SignalCategory } from "@/types/signal";

// ─────────────────────────────────────────────────────────────────────────────
// Sync phase dialog
// ─────────────────────────────────────────────────────────────────────────────

const SYNC_PHASES = [
  {
    key: "equity",
    label:  "Phase 1 — NSE Equity List",
    detail: "Downloads ~1,900 EQ-series stocks from NSE EQUITY_L.csv",
  },
  {
    key: "index_flags",
    label:  "Phase 2 — Index Memberships",
    detail: "Sets Nifty 50 / Next 50 / 500 / Midcap / Smallcap / F&O flags",
  },
  {
    key: "fundamentals",
    label:  "Phase 3 — Fundamentals (yfinance)",
    detail: "Enriches sector, PE, PB, market cap for pending stocks (batch, rate-limited)",
  },
];

function SyncDialog({
  open,
  phases,
  onClose,
  onConfirm,
  syncing,
}: {
  open: boolean;
  phases: string[];
  onClose: () => void;
  onConfirm: (phases: string[]) => void;
  syncing: boolean;
}) {
  const activeSteps = SYNC_PHASES.filter((p) => phases.includes(p.key));
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {phases.length === 3 ? "Full Stock Master Sync" : "Sync Index Memberships"}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" mb={2}>
          The following phases will be queued as a background Celery task. This may take several minutes.
        </Typography>
        <Stepper orientation="vertical" nonLinear>
          {activeSteps.map((p) => (
            <Step key={p.key} active completed={false}>
              <StepLabel>
                <Typography variant="body2" fontWeight={600}>{p.label}</Typography>
                <Typography variant="caption" color="text.secondary">{p.detail}</Typography>
              </StepLabel>
            </Step>
          ))}
        </Stepper>
        {phases.includes("fundamentals") && (
          <Alert severity="info" sx={{ mt: 2, fontSize: "0.78rem" }}>
            Phase 3 processes all pending stocks in batches of 50. Progress is shown live on this page — buttons are disabled until the sync finishes.
          </Alert>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={syncing}>Cancel</Button>
        <Button
          variant="contained"
          onClick={() => onConfirm(phases)}
          disabled={syncing}
          startIcon={syncing ? <CircularProgress size={14} color="inherit" /> : <Sync />}
        >
          {syncing ? "Queuing…" : "Queue Sync"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sync progress card
// ─────────────────────────────────────────────────────────────────────────────

const PHASE_LABEL: Record<string, string> = {
  equity:       "Phase 1 — Downloading NSE equity list",
  index_flags:  "Phase 2 — Updating index memberships",
  fundamentals: "Phase 3 — Enriching fundamentals (yfinance)",
};

function SyncProgressCard({ status }: { status: SyncTaskStatus }) {
  if (status.state === "idle") return null;

  const isRunning  = status.is_running;
  const isSuccess  = status.state === "SUCCESS";
  const isFailure  = status.state === "FAILURE";

  const borderColor = isSuccess
    ? "rgba(34,197,94,0.3)"
    : isFailure
    ? "rgba(239,68,68,0.3)"
    : "rgba(99,102,241,0.3)";

  const phaseLabel = status.current_phase
    ? PHASE_LABEL[status.current_phase] ?? status.current_phase
    : "Initialising…";

  return (
    <Card sx={{ mb: 2, border: "1px solid", borderColor, bgcolor: "transparent" }}>
      <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
        {/* Title row */}
        <Box display="flex" alignItems="center" gap={1} mb={isRunning ? 0.8 : 0}>
          {isRunning  && <CircularProgress size={14} thickness={5} />}
          {isSuccess  && <CheckCircle sx={{ fontSize: 16, color: "success.main" }} />}
          {isFailure  && <ErrorOutline sx={{ fontSize: 16, color: "error.main" }} />}
          <Typography variant="body2" fontWeight={600}>
            {isRunning  && `Sync running — ${phaseLabel}`}
            {isSuccess  && "Sync completed successfully"}
            {isFailure  && `Sync failed: ${status.error ?? "unknown error"}`}
          </Typography>
          {status.started_at && (
            <Typography variant="caption" color="text.disabled" ml="auto">
              started {formatIST(status.started_at)}
            </Typography>
          )}
        </Box>

        {/* Progress bar (running only) */}
        {isRunning && (
          <LinearProgress variant="indeterminate" sx={{ height: 3, borderRadius: 2, mb: 0.8 }} />
        )}

        {/* Fundamentals batch counters */}
        {status.progress && (
          <Stack direction="row" spacing={2.5} mt={0.3}>
            <Typography variant="caption" color="text.secondary">
              Processed: <strong>{status.progress.processed.toLocaleString()}</strong>
            </Typography>
            <Typography variant="caption" color="success.light">
              ✓ {status.progress.succeeded.toLocaleString()} enriched
            </Typography>
            {status.progress.failed > 0 && (
              <Typography variant="caption" color="error.light">
                ✗ {status.progress.failed} failed
              </Typography>
            )}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}

const INDEX_OPTIONS = [
  { value: "", label: "All Indices" },
  { value: "nifty50", label: "Nifty 50" },
  { value: "nifty_next50", label: "Nifty Next 50" },
  { value: "nifty100", label: "Nifty 100" },
  { value: "nifty500", label: "Nifty 500" },
  { value: "midcap150", label: "Midcap 150" },
  { value: "smallcap100", label: "Smallcap 100" },
  { value: "fno", label: "F&O Eligible" },
];

const CATEGORY_OPTIONS = [
  { value: "",           label: "All Signals"    },
  { value: "INVESTMENT", label: "Long-Term Buy"  },
  { value: "SWING",      label: "Swing Buy"      },
  { value: "POSITIONAL", label: "Positional Buy" },
  { value: "WATCH",      label: "Watch"          },
  { value: "IGNORE",     label: "No Action"      },
];

export default function StocksPage() {
  const router   = useRouter();
  const dispatch = useDispatch<AppDispatch>();
  const { enqueueSnackbar } = useSnackbar();

  // ── Stock master sync status ───────────────────────────────────────────────
  const { data: syncStatus, refetch: refetchSyncStatus } = useGetSyncStatusQuery(undefined, {
    pollingInterval: 5000,
  });
  const syncRunning    = syncStatus?.is_running ?? false;
  const prevRunningRef = useRef(false);

  // Detect sync completion → notify + refresh stats
  useEffect(() => {
    if (prevRunningRef.current && !syncRunning && syncStatus) {
      if (syncStatus.state === "SUCCESS") {
        const p = syncStatus.progress;
        enqueueSnackbar(
          p
            ? `Sync complete — ${p.succeeded.toLocaleString()} enriched, ${p.failed} failed`
            : "Sync completed successfully",
          { variant: "success", autoHideDuration: 6000 },
        );
      } else if (syncStatus.state === "FAILURE") {
        enqueueSnackbar(`Sync failed: ${syncStatus.error ?? "unknown error"}`, {
          variant: "error",
          autoHideDuration: 8000,
        });
      }
      dispatch(stockMasterApi.util.invalidateTags(["StockSync", "Stock"]));
    }
    prevRunningRef.current = syncRunning;
  }, [syncRunning, syncStatus, dispatch, enqueueSnackbar]);

  // Live scan state from WebSocket
  const scanProgress       = useSelector(selectScanProgress);
  const isScanning         = useSelector(selectIsScanning);
  const hasRealProgress    = useSelector(selectHasRealProgress);
  const progressPct        = useSelector(selectScanProgressPct);
  const streamingCount     = useSelector(selectStreamingCount);

  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({ page: 0, pageSize: 100 });
  const [sector, setSector] = useState("");
  const [indexFilter, setIndexFilter] = useState("");
  const [exchange, setExchange] = useState("");
  const [category, setCategory] = useState("");
  const [appliedFilters, setAppliedFilters] = useState<StockFilters>({});
  const [syncDialog, setSyncDialog] = useState<string[] | null>(null);

  const activeFilters: StockFilters = {
    ...appliedFilters,
    limit: paginationModel.pageSize,
    offset: paginationModel.page * paginationModel.pageSize,
  };

  const { data, isLoading } = useListStocksQuery(activeFilters);
  const { data: stats, isLoading: statsLoading } = useGetStockStatsQuery();
  const [triggerSync, { isLoading: syncing }] = useTriggerSyncMutation();

  const handleSyncConfirm = async (phases: string[]) => {
    try {
      const result = await triggerSync({ phases }).unwrap();
      enqueueSnackbar(
        `${phases.length === 3 ? "Full sync" : "Index sync"} queued (${result.task_id.slice(0, 8)}…)`,
        { variant: "info", autoHideDuration: 4000 },
      );
      setSyncDialog(null);
      // Start polling immediately
      refetchSyncStatus();
    } catch {
      enqueueSnackbar("Failed to queue sync — is Celery running?", { variant: "error" });
    }
  };

  const applyFilters = useCallback(() => {
    setAppliedFilters({
      ...(sector      ? { sector }      : {}),
      ...(indexFilter ? { index_filter: indexFilter as StockFilters["index_filter"] } : {}),
      ...(exchange    ? { exchange: exchange as "NSE" | "BSE" } : {}),
      ...(category    ? { category }    : {}),
    });
    setPaginationModel((p) => ({ ...p, page: 0 }));
  }, [sector, indexFilter, exchange, category]);

  const clearFilters = () => {
    setSector(""); setIndexFilter(""); setExchange(""); setCategory("");
    setAppliedFilters({});
    setPaginationModel((p) => ({ ...p, page: 0 }));
  };

  const handleRowClick = (params: GridRowParams<Stock>) => {
    router.push(`/stocks/${params.row.symbol}`);
  };

  const columns: GridColDef<Stock>[] = [
    {
      field: "symbol",
      headerName: "Symbol",
      width: 130,
      renderCell: (p) => (
        <Box>
          <Typography variant="body2" fontWeight={700} color="primary.light" lineHeight={1.2}>
            {p.value}
          </Typography>
          {p.row.company_name && (
            <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block", maxWidth: 120, fontSize: "0.65rem" }}>
              {p.row.company_name}
            </Typography>
          )}
        </Box>
      ),
    },
    {
      field: "sector",
      headerName: "Sector",
      width: 130,
      renderCell: (p) => p.value ?? <Typography color="text.disabled" variant="caption">—</Typography>,
    },
    {
      field: "market_cap",
      headerName: "Mkt Cap",
      width: 100,
      renderCell: (p) =>
        p.value ? (
          <Typography variant="body2" sx={{ fontVariantNumeric: "tabular-nums" }}>
            {formatCompact(p.value)}
          </Typography>
        ) : <Typography color="text.disabled" variant="caption">—</Typography>,
    },
    {
      field: "_live_price",
      headerName: "Price",
      width: 90,
      sortable: false,
      renderCell: (p) => {
        const price = p.row.live_price;
        return price ? (
          <Typography variant="body2" sx={{ fontVariantNumeric: "tabular-nums" }}>
            {formatPrice(price)}
          </Typography>
        ) : p.row.latest_entry ? (
          <Tooltip title="Last scan price">
            <Typography variant="body2" color="text.secondary" sx={{ fontVariantNumeric: "tabular-nums" }}>
              {formatPrice(p.row.latest_entry)}
            </Typography>
          </Tooltip>
        ) : <Typography color="text.disabled" variant="caption">—</Typography>;
      },
    },
    {
      field: "latest_category",
      headerName: "Signal Status",
      width: 130,
      renderCell: (p) => p.value
        ? <CategoryChip category={p.value as SignalCategory} chipSize="xs" />
        : <Typography color="text.disabled" variant="caption">—</Typography>,
    },
    {
      field: "latest_gate_strength",
      headerName: "GATE",
      width: 130,
      renderCell: (p) =>
        p.value != null ? <GATEBar score={p.value} /> : <Typography color="text.disabled" variant="caption">—</Typography>,
    },
    {
      field: "latest_rank_score",
      headerName: "Rank",
      width: 65,
      renderCell: (p) =>
        p.value != null ? (
          <Typography variant="body2" fontWeight={600}>{Math.round(p.value)}</Typography>
        ) : <Typography color="text.disabled" variant="caption">—</Typography>,
    },
    {
      field: "latest_signal_timeframe",
      headerName: "TF",
      width: 60,
      renderCell: (p) =>
        p.value ? (
          <Chip label={p.value} size="small" sx={{ fontSize: "0.68rem", height: 18 }} />
        ) : null,
    },
    {
      field: "latest_entry",
      headerName: "Entry",
      width: 85,
      renderCell: (p) =>
        p.value ? (
          <Typography variant="body2" sx={{ fontVariantNumeric: "tabular-nums" }}>
            {formatPrice(p.value)}
          </Typography>
        ) : <Typography color="text.disabled" variant="caption">—</Typography>,
    },
    {
      field: "latest_stop_loss",
      headerName: "SL",
      width: 85,
      renderCell: (p) =>
        p.value ? (
          <Typography variant="body2" color="error.light" sx={{ fontVariantNumeric: "tabular-nums" }}>
            {formatPrice(p.value)}
          </Typography>
        ) : <Typography color="text.disabled" variant="caption">—</Typography>,
    },
    {
      field: "latest_t1",
      headerName: "T1",
      width: 85,
      renderCell: (p) =>
        p.value ? (
          <Typography variant="body2" color="success.light" sx={{ fontVariantNumeric: "tabular-nums" }}>
            {formatPrice(p.value)}
          </Typography>
        ) : <Typography color="text.disabled" variant="caption">—</Typography>,
    },
    {
      field: "latest_rr_t1",
      headerName: "RR",
      width: 60,
      renderCell: (p) =>
        p.value ? (
          <Typography variant="body2" fontWeight={600} color={p.value >= 2 ? "success.main" : "text.primary"}>
            {formatRR(p.value)}
          </Typography>
        ) : <Typography color="text.disabled" variant="caption">—</Typography>,
    },
    {
      field: "in_nifty50",
      headerName: "N50",
      width: 48,
      renderCell: (p) =>
        p.value ? <Chip label="✓" size="small" color="success" sx={{ height: 18, fontSize: 10 }} /> : null,
    },
    {
      field: "is_fno",
      headerName: "F&O",
      width: 48,
      renderCell: (p) =>
        p.value ? <Chip label="✓" size="small" color="primary" sx={{ height: 18, fontSize: 10 }} /> : null,
    },
  ];

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2.5}>
        <Box>
          <Typography variant="h6" fontWeight={700}>Stock Master</Typography>
          <Typography variant="caption" color="text.secondary">
            Central registry · click any row to view GATE chart and analysis
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          {syncRunning && (
            <Chip
              icon={<CircularProgress size={12} color="inherit" />}
              label="Sync running…"
              size="small"
              color="primary"
              variant="outlined"
              sx={{ fontSize: "0.72rem" }}
            />
          )}
          <Tooltip title={syncRunning ? "A sync is already running" : ""} disableHoverListener={!syncRunning}>
            <span>
              <Button
                variant="outlined" size="small"
                startIcon={<Sync />}
                disabled={syncing || syncRunning}
                onClick={() => setSyncDialog(["equity", "index_flags"])}
              >
                Sync Indices
              </Button>
            </span>
          </Tooltip>
          <Tooltip title={syncRunning ? "A sync is already running" : ""} disableHoverListener={!syncRunning}>
            <span>
              <Button
                variant="contained" size="small"
                startIcon={<Sync />}
                disabled={syncing || syncRunning}
                onClick={() => setSyncDialog(["equity", "index_flags", "fundamentals"])}
              >
                Full Sync
              </Button>
            </span>
          </Tooltip>
        </Stack>
      </Box>

      {/* Sync stats */}
      <Grid container spacing={2} mb={2}>
        <Grid item xs={6} sm={3}>
          <StatCard label="Total Stocks" value={statsLoading ? "…" : (stats?.total ?? 0).toLocaleString()} icon={<Info />} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatCard label="Enriched" value={statsLoading ? "…" : (stats?.by_sync_status?.enriched ?? 0).toLocaleString()} color={STATUS_COLORS.INVESTMENT} icon={<CheckCircle />} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatCard label="Pending" value={statsLoading ? "…" : (stats?.by_sync_status?.pending ?? 0).toLocaleString()} color={STATUS_COLORS.WATCH} icon={<Schedule />} subtitle="awaiting yfinance" />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatCard label="Failed" value={statsLoading ? "…" : (stats?.by_sync_status?.failed ?? 0).toLocaleString()} color={GATE_COLOR.FAIL} icon={<ErrorOutline />} subtitle="retry in 6 h" />
        </Grid>
      </Grid>

      {/* Stock master sync progress */}
      {syncStatus && <SyncProgressCard status={syncStatus} />}

      {/* Scan progress banner */}
      {isScanning && (
        <Box mb={2}>
          <Alert
            severity="info"
            icon={<CircularProgress size={16} />}
            sx={{ mb: 0.5, py: 0.5 }}
          >
            <strong>Scan running</strong> — GATE results will appear automatically when complete.
            {hasRealProgress
              ? ` ${scanProgress!.done}/${scanProgress!.total} symbols analysed · ${streamingCount} signals found so far`
              : " Fetching data…"}
          </Alert>
          <LinearProgress
            variant={hasRealProgress ? "determinate" : "indeterminate"}
            value={hasRealProgress ? progressPct : undefined}
            sx={{ height: 3, borderRadius: 0 }}
          />
        </Box>
      )}

      {/* Filters */}
      <Stack direction="row" spacing={1.5} mb={2} flexWrap="wrap" useFlexGap alignItems="center">
        <FormControl size="small" sx={{ minWidth: 130 }}>
          <InputLabel>Index</InputLabel>
          <Select value={indexFilter} label="Index" onChange={(e) => setIndexFilter(e.target.value)}>
            {INDEX_OPTIONS.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 130 }}>
          <InputLabel>Signal</InputLabel>
          <Select value={category} label="Signal" onChange={(e) => setCategory(e.target.value)}>
            {CATEGORY_OPTIONS.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 100 }}>
          <InputLabel>Exchange</InputLabel>
          <Select value={exchange} label="Exchange" onChange={(e) => setExchange(e.target.value)}>
            <MenuItem value="">All</MenuItem>
            <MenuItem value="NSE">NSE</MenuItem>
            <MenuItem value="BSE">BSE</MenuItem>
          </Select>
        </FormControl>
        <TextField
          size="small" label="Sector" placeholder="e.g. Banking"
          value={sector} onChange={(e) => setSector(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && applyFilters()}
          sx={{ width: 150 }}
        />
        <Button variant="outlined" size="small" onClick={applyFilters}>Apply</Button>
        <Button size="small" onClick={clearFilters}>Clear</Button>
        {data && (
          <Typography variant="caption" color="text.secondary" ml="auto">
            {data.total.toLocaleString()} stocks
          </Typography>
        )}
      </Stack>

      {/* Data grid */}
      <DataGrid
        aria-label="Stock master list"
        rows={data?.items ?? []}
        columns={columns}
        loading={isLoading}
        rowCount={data?.total ?? 0}
        paginationMode="server"
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        pageSizeOptions={[25, 50, 100]}
        getRowId={(r: Stock) => `${r.symbol}-${r.exchange}`}
        onRowClick={handleRowClick}
        density="compact"
        disableRowSelectionOnClick
        getRowHeight={() => "auto"}
        sx={{
          border: "none",
          minHeight: 480,
          "& .MuiDataGrid-row": { cursor: "pointer" },
          "& .MuiDataGrid-row:hover": { bgcolor: "rgba(99,102,241,0.06)" },
          "& .MuiDataGrid-columnHeaders": { bgcolor: "rgba(255,255,255,0.03)" },
        }}
      />

      {/* Sync phase dialog */}
      <SyncDialog
        open={syncDialog !== null}
        phases={syncDialog ?? []}
        onClose={() => setSyncDialog(null)}
        onConfirm={handleSyncConfirm}
        syncing={syncing}
      />
    </Box>
  );
}
