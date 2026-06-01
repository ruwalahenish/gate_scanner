"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Box, Typography, Grid, Chip, Button, TextField,
  Select, MenuItem, FormControl, InputLabel, Stack, Tooltip,
  CircularProgress, Alert, LinearProgress,
  Dialog, DialogTitle, DialogContent, DialogActions, Stepper, Step, StepLabel,
} from "@mui/material";
import { DataGrid, type GridColDef, type GridPaginationModel, type GridRowParams } from "@mui/x-data-grid";
import { Sync, CheckCircle, Schedule, ErrorOutline, Info } from "@mui/icons-material";
import { useSnackbar } from "notistack";
import { useSelector } from "react-redux";
import { StatCard } from "@/components/ui/StatCard";
import { GATEBar } from "@/components/ui/GATEBar";
import { formatCompact, formatPrice, formatIST, formatRR } from "@/lib/formatters";
import {
  useListStocksQuery,
  useGetStockStatsQuery,
  useTriggerSyncMutation,
} from "@/store/api/stockMasterApi";
import type { RootState } from "@/store";
import type { StockFilters, Stock } from "@/types/stock";

// ─────────────────────────────────────────────────────────────────────────────
// Business-terminology status chip for signal column
// ─────────────────────────────────────────────────────────────────────────────

const SIGNAL_DISPLAY: Record<string, { label: string; color: string }> = {
  INVESTMENT: { label: "Long-Term Buy",  color: "#22c55e" },
  SWING:      { label: "Swing Buy",      color: "#6366f1" },
  POSITIONAL: { label: "Positional Buy", color: "#38bdf8" },
  WATCH:      { label: "Watch",          color: "#f59e0b" },
  IGNORE:     { label: "No Action",      color: "#64748b" },
};

function SignalStatusChip({ category }: { category: string | null }) {
  if (!category) return <Typography variant="caption" color="text.disabled">—</Typography>;
  const { label, color } = SIGNAL_DISPLAY[category] ?? { label: category, color: "#64748b" };
  return (
    <Chip
      label={label}
      size="small"
      sx={{
        bgcolor: `${color}1a`,
        color,
        border: `1px solid ${color}40`,
        fontWeight: 600,
        fontSize: "0.62rem",
        height: 20,
        maxWidth: 120,
      }}
    />
  );
}

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
          {activeSteps.map((p, i) => (
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
            Phase 3 enriches stocks in batches of 50 and may run for 10–30 minutes depending on the queue size.
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
  const router = useRouter();
  const { enqueueSnackbar } = useSnackbar();

  // Live scan state from WebSocket
  const scanProgress      = useSelector((s: RootState) => s.ws.scanProgress);
  const streamingSignals  = useSelector((s: RootState) => s.ws.streamingSignals);
  const isScanning        = scanProgress !== null;
  const hasRealProgress   = isScanning && (scanProgress?.total ?? 0) > 0;
  const progressPct       = hasRealProgress
    ? Math.min(100, Math.round(((scanProgress?.done ?? 0) / (scanProgress?.total ?? 1)) * 100))
    : 0;

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
        `${phases.length === 3 ? "Full sync" : "Index sync"} queued (${result.task_id.slice(0, 8)}…) — running in background`,
        { variant: "success", autoHideDuration: 5000 }
      );
      setSyncDialog(null);
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
      renderCell: (p) => <SignalStatusChip category={p.value} />,
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
        <Stack direction="row" spacing={1}>
          <Button
            variant="outlined" size="small"
            startIcon={<Sync />}
            disabled={syncing}
            onClick={() => setSyncDialog(["equity", "index_flags"])}
          >
            Sync Indices
          </Button>
          <Button
            variant="contained" size="small"
            startIcon={<Sync />}
            disabled={syncing}
            onClick={() => setSyncDialog(["equity", "index_flags", "fundamentals"])}
          >
            Full Sync
          </Button>
        </Stack>
      </Box>

      {/* Sync stats */}
      <Grid container spacing={2} mb={2}>
        <Grid item xs={6} sm={3}>
          <StatCard label="Total Stocks" value={statsLoading ? "…" : (stats?.total ?? 0).toLocaleString()} icon={<Info />} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatCard label="Enriched" value={statsLoading ? "…" : (stats?.by_sync_status?.enriched ?? 0).toLocaleString()} color="#22c55e" icon={<CheckCircle />} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatCard label="Pending" value={statsLoading ? "…" : (stats?.by_sync_status?.pending ?? 0).toLocaleString()} color="#f59e0b" icon={<Schedule />} subtitle="awaiting yfinance" />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatCard label="Failed" value={statsLoading ? "…" : (stats?.by_sync_status?.failed ?? 0).toLocaleString()} color="#ef4444" icon={<ErrorOutline />} subtitle="retry in 6 h" />
        </Grid>
      </Grid>

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
              ? ` ${scanProgress!.done}/${scanProgress!.total} symbols analysed · ${streamingSignals.length} signals found so far`
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
