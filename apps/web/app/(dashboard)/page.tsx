"use client";
import {
  Box, Grid, Card, CardContent, Typography, Chip,
  Divider, LinearProgress, Stack, CircularProgress,
} from "@mui/material";
import {
  TrendingUp, SwapHoriz, EmojiEvents,
  CheckCircleOutline, ErrorOutline, AccessTime,
} from "@mui/icons-material";
import { useSelector } from "react-redux";
import { memo } from "react";
import { StatCard } from "@/components/ui/StatCard";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageError } from "@/components/ui/PageError";
import { PnlBadge } from "@/components/ui/PnlBadge";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { StockLink } from "@/components/ui/StockLink";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useGetDashboardQuery } from "@/store/api/scannerApi";
import { formatIST, formatPrice, formatRR } from "@/lib/formatters";
import { STATUS_COLORS, EXIT_LABEL } from "@/lib/constants";
import {
  selectScanProgress,
  selectLastPostProcess,
  selectHasRealProgress,
  selectScanProgressPct,
} from "@/store/selectors";
import type { DashboardData } from "@/store/api/scannerApi";
import type { SignalCategory } from "@/types/signal";

// ─────────────────────────────────────────────────────────────────────────────
// Small inline helpers
// ─────────────────────────────────────────────────────────────────────────────

function HealthDot({ ok }: { ok: boolean }) {
  return ok
    ? <CheckCircleOutline
        sx={{ fontSize: 16, color: "success.main" }}
        aria-label="Healthy"
        titleAccess={ok ? "Healthy" : "Error"}
      />
    : <ErrorOutline
        sx={{ fontSize: 16, color: "error.main" }}
        aria-label="Error"
        titleAccess="Error"
      />;
}

// ─────────────────────────────────────────────────────────────────────────────
// Section: Recent BUY Opportunities
// ─────────────────────────────────────────────────────────────────────────────

const OpportunitiesSection = memo(function OpportunitiesSection({ items }: { items: DashboardData["recent_opportunities"] }) {
  if (!items || items.length === 0) {
    return (
      <EmptyState
        title="No BUY opportunities yet"
        description="Run a GATE scan to discover opportunities"
      />
    );
  }

  const OPTY_HEADERS = ["Symbol", "Status", "GATE", "Entry", "RR"];
  return (
    <Stack spacing={0}>
      {/* Column headers */}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "90px 1fr 48px 64px 56px",
          gap: 1,
          px: 0.5,
          pb: 0.5,
        }}
      >
        {OPTY_HEADERS.map((h) => (
          <Typography key={h} variant="caption" color="text.disabled" textAlign={h === "Symbol" || h === "Status" ? "left" : "right"}>
            {h}
          </Typography>
        ))}
      </Box>
      {items.map((sig) => {
        return (
          <Box
            key={sig.id}
            sx={{
              display: "grid",
              gridTemplateColumns: "90px 1fr 48px 64px 56px",
              alignItems: "center",
              gap: 1,
              py: 0.9,
              px: 0.5,
              borderBottom: "1px solid rgba(255,255,255,0.04)",
              "&:last-child": { borderBottom: "none" },
              "&:hover": { bgcolor: "rgba(255,255,255,0.025)", borderRadius: 1 },
            }}
          >
            {/* Symbol */}
            <StockLink symbol={sig.symbol} variant="body2" fontWeight={700} noWrap />

            {/* Category chip */}
            <CategoryChip
              category={(sig.category ?? "IGNORE") as SignalCategory}
              chipSize="xs"
            />

            {/* GATE score */}
            <Typography variant="caption" color="text.secondary" textAlign="right">
              {sig.gate_strength != null ? sig.gate_strength.toFixed(0) : "—"}
            </Typography>

            {/* Entry */}
            <Typography variant="caption" noWrap textAlign="right">
              {formatPrice(sig.entry)}
            </Typography>

            {/* RR */}
            <Typography
              variant="caption"
              textAlign="right"
              color={sig.rr_t1 != null && sig.rr_t1 >= 2 ? "success.main" : "text.secondary"}
            >
              {formatRR(sig.rr_t1)}
            </Typography>
          </Box>
        );
      })}
    </Stack>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Section: Recent Paper Trades
// ─────────────────────────────────────────────────────────────────────────────

const RecentTradesSection = memo(function RecentTradesSection({ items }: { items: DashboardData["recent_trades"] }) {
  type TradeRow = {
    id: string; symbol: string; pnl_abs?: number | null;
    pnl_pct?: number | null; exit_reason?: string | null; executed_at?: string;
  };

  const trades = items as TradeRow[];

  if (!trades || trades.length === 0) {
    return (
      <EmptyState
        title="No paper trades yet"
        description="Trades are created automatically from BUY signals"
      />
    );
  }

  return (
    <Stack spacing={0}>
      {/* Column headers */}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "80px 1fr 80px 70px",
          gap: 1,
          px: 0.5,
          pb: 0.5,
        }}
      >
        {["Symbol", "Exit Reason", "P&L", "Date"].map((h) => (
          <Typography key={h} variant="caption" color="text.disabled" textAlign={h === "Symbol" || h === "Exit Reason" ? "left" : "right"}>
            {h}
          </Typography>
        ))}
      </Box>
      {trades.map((t) => {
        const isWin = (t.pnl_abs ?? 0) >= 0;
        return (
          <Box
            key={t.id}
            sx={{
              display: "grid",
              gridTemplateColumns: "80px 1fr 80px 70px",
              alignItems: "center",
              gap: 1,
              py: 0.9,
              px: 0.5,
              borderBottom: "1px solid rgba(255,255,255,0.04)",
              "&:last-child": { borderBottom: "none" },
              "&:hover": { bgcolor: "rgba(255,255,255,0.025)", borderRadius: 1 },
            }}
          >
            <StockLink symbol={t.symbol} variant="body2" fontWeight={700} noWrap />
            <Typography variant="caption" color="text.secondary" noWrap>
              {EXIT_LABEL[t.exit_reason ?? ""] ?? t.exit_reason ?? "—"}
            </Typography>
            <Typography
              variant="caption"
              fontWeight={600}
              textAlign="right"
              color={isWin ? "success.main" : "error.main"}
              noWrap
            >
              {t.pnl_abs != null ? `${isWin ? "+" : ""}${formatPrice(t.pnl_abs, 0)}` : "—"}
            </Typography>
            <Typography variant="caption" color="text.secondary" textAlign="right" noWrap>
              {t.executed_at ? formatIST(t.executed_at) : "—"}
            </Typography>
          </Box>
        );
      })}
    </Stack>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Section: Paper Trading P&L mini-panel
// ─────────────────────────────────────────────────────────────────────────────

const PaperTradingPanel = memo(function PaperTradingPanel({ pt }: { pt: DashboardData["paper_trading"] }) {
  return (
    <Stack spacing={0.6}>
      <Typography variant="caption" color="text.secondary" fontWeight={600} mb={0.3}>
        PAPER TRADING
      </Typography>
      {[
        { label: "Total P&L",      value: <PnlBadge pnl={pt.total_pnl} variant="caption" showIcon /> },
        { label: "Realized",       value: <PnlBadge pnl={pt.realized_pnl} variant="caption" /> },
        { label: "Unrealized",     value: <PnlBadge pnl={pt.unrealized_pnl} variant="caption" /> },
        { label: "Win Rate",       value: <Typography variant="caption" fontWeight={600}>{pt.win_rate.toFixed(1)}%</Typography> },
        { label: "Open Positions", value: <Typography variant="caption" fontWeight={600}>{pt.open_positions}</Typography> },
      ].map(({ label, value }) => (
        <Box key={label} display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="caption" color="text.secondary">{label}</Typography>
          {value}
        </Box>
      ))}
    </Stack>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Section: System Health mini-panel
// ─────────────────────────────────────────────────────────────────────────────

const SystemHealthPanel = memo(function SystemHealthPanel({ health, scanner }: {
  health: DashboardData["system_health"];
  scanner: DashboardData["scanner"];
}) {
  return (
    <Stack spacing={0.6}>
      <Typography variant="caption" color="text.secondary" fontWeight={600} mb={0.3}>
        SYSTEM HEALTH
      </Typography>
      {[
        { label: "Database",    node: <HealthDot ok={health.db_ok} /> },
        { label: "Redis Cache", node: <HealthDot ok={health.redis_ok} /> },
      ].map(({ label, node }) => (
        <Box key={label} display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="caption" color="text.secondary">{label}</Typography>
          {node}
        </Box>
      ))}
      <Divider sx={{ borderColor: "rgba(255,255,255,0.06)", my: 0.3 }} />
      <Box display="flex" justifyContent="space-between">
        <Typography variant="caption" color="text.secondary">Last Scan</Typography>
        <Typography variant="caption" fontWeight={600}>
          {scanner.last_scan_at ? formatIST(scanner.last_scan_at) : "Never"}
        </Typography>
      </Box>
      {health.last_scan_duration_sec != null && (
        <Box display="flex" justifyContent="space-between">
          <Typography variant="caption" color="text.secondary">Duration</Typography>
          <Typography variant="caption" fontWeight={600}>
            {health.last_scan_duration_sec.toFixed(0)}s
          </Typography>
        </Box>
      )}
      <Box display="flex" justifyContent="space-between">
        <Typography variant="caption" color="text.secondary">Backtests</Typography>
        <Typography variant="caption" fontWeight={600}>
          —
        </Typography>
      </Box>
    </Stack>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Main dashboard page
// ─────────────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { data, isLoading, isError, refetch } = useGetDashboardQuery(undefined, {
    pollingInterval: 60_000,
    skipPollingIfUnfocused: true,
  });

  const scanProgress    = useSelector(selectScanProgress);
  const lastProcess     = useSelector(selectLastPostProcess);
  const hasRealProgress = useSelector(selectHasRealProgress);
  const progressPct     = useSelector(selectScanProgressPct);

  // ── Scan in-progress banner ────────────────────────────────────────────
  const ScanBanner = scanProgress ? (
    <Card sx={{ mb: 2, bgcolor: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)" }}>
      <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.8}>
          <Box display="flex" alignItems="center" gap={1}>
            <CircularProgress size={14} thickness={5} />
            <Typography variant="body2" fontWeight={600}>Scanning in progress…</Typography>
          </Box>
          {hasRealProgress && (
            <Typography variant="caption" color="text.secondary">
              {scanProgress.done} / {scanProgress.total} symbols ({progressPct}%)
            </Typography>
          )}
        </Box>
        <LinearProgress
          variant={hasRealProgress ? "determinate" : "indeterminate"}
          value={hasRealProgress ? progressPct : undefined}
          sx={{ height: 4, borderRadius: 2 }}
        />
      </CardContent>
    </Card>
  ) : null;

  // ── Post-process notification ──────────────────────────────────────────
  const PostProcessBanner = lastProcess && !scanProgress && lastProcess.trades_created > 0 ? (
    <Card sx={{ mb: 2, bgcolor: "rgba(34,197,94,0.06)", border: "1px solid rgba(34,197,94,0.15)" }}>
      <CardContent sx={{ py: 1, "&:last-child": { pb: 1 } }}>
        <Typography variant="caption" color="success.light">
          Last scan: {lastProcess.trades_created} paper trade{lastProcess.trades_created !== 1 ? "s" : ""} created automatically
        </Typography>
      </CardContent>
    </Card>
  ) : null;

  // ── Loading skeleton ───────────────────────────────────────────────────
  if (isLoading) {
    return (
      <Box>
        <Typography variant="h6" fontWeight={700} mb={2}>Dashboard</Typography>
        <Grid container spacing={2} mb={2}>
          {[1, 2, 3, 4].map((i) => (
            <Grid item xs={6} sm={3} key={i}>
              <SkeletonCard rows={2} />
            </Grid>
          ))}
        </Grid>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}><SkeletonCard rows={5} /></Grid>
          <Grid item xs={12} md={6}><SkeletonCard rows={5} /></Grid>
        </Grid>
      </Box>
    );
  }

  if (isError) {
    return (
      <Box>
        <Typography variant="h6" fontWeight={700} mb={2}>Dashboard</Typography>
        <Card>
          <PageError
            message="Could not load dashboard data"
            detail="Check that the backend API is running and the database is reachable"
            onRetry={refetch}
          />
        </Card>
      </Box>
    );
  }

  if (!data) return null;

  const { scanner, paper_trading, backtesting, recent_opportunities, recent_trades, system_health } = data;

  // ── No scan yet — onboarding state ────────────────────────────────────
  if (!scanner.last_scan_at) {
    return (
      <Box>
        <Typography variant="h6" fontWeight={700} mb={2}>Dashboard</Typography>
        {ScanBanner}
        <Card>
          <EmptyState
            icon={<TrendingUp />}
            title="Run your first GATE scan"
            description="The dashboard will populate with signals and paper trades after your first scan completes."
          />
        </Card>
      </Box>
    );
  }

  return (
    <Box>
      {/* Page title + scan meta */}
      <Box display="flex" alignItems="baseline" gap={1.5} mb={2} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>Dashboard</Typography>
        <Box display="flex" alignItems="center" gap={0.5}>
          <AccessTime sx={{ fontSize: 13, color: "text.disabled" }} />
          <Typography variant="caption" color="text.secondary">
            Last scan: {formatIST(scanner.last_scan_at)}
          </Typography>
        </Box>
        {backtesting.last_run_at && (
          <Typography variant="caption" color="text.disabled">
            · Best backtest CAGR: {backtesting.best_cagr.toFixed(1)}%
          </Typography>
        )}
      </Box>

      {ScanBanner}
      {PostProcessBanner}

      {/* ── Stat bar ─────────────────────────────────────────────────────── */}
      <Grid container spacing={2} mb={2}>
        <Grid item xs={6} sm={3}>
          <StatCard
            label="BUY Signals"
            value={scanner.buy_count}
            subtitle={`${scanner.watch_count} watching`}
            icon={<TrendingUp />}
            color={STATUS_COLORS.INVESTMENT}
          />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatCard
            label="Open Trades"
            value={paper_trading.open_positions}
            subtitle={`${paper_trading.total_trades} total`}
            icon={<SwapHoriz />}
            color={STATUS_COLORS.SWING}
          />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatCard
            label="Win Rate"
            value={`${paper_trading.win_rate.toFixed(1)}%`}
            subtitle={`${paper_trading.winning_trades}W / ${paper_trading.total_trades - paper_trading.winning_trades}L`}
            icon={<EmojiEvents />}
            color={paper_trading.win_rate >= 50 ? STATUS_COLORS.INVESTMENT : "#ef4444"}
            trend={paper_trading.win_rate >= 50 ? "up" : "down"}
          />
        </Grid>
      </Grid>

      {/* ── Main content: opportunities + trades ─────────────────────────── */}
      <Grid container spacing={2} mb={2}>
        <Grid item xs={12} md={6}>
          <ErrorBoundary>
            <Card sx={{ height: "100%" }}>
              <CardContent sx={{ pb: "12px !important" }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                  <Typography variant="subtitle2" fontWeight={700}>Recent BUY Opportunities</Typography>
                  <Chip
                    label={`${recent_opportunities.length} shown`}
                    size="small"
                    sx={{ fontSize: "0.65rem", height: 18 }}
                  />
                </Box>
                <OpportunitiesSection items={recent_opportunities} />
              </CardContent>
            </Card>
          </ErrorBoundary>
        </Grid>

        <Grid item xs={12} md={6}>
          <ErrorBoundary>
            <Card sx={{ height: "100%" }}>
              <CardContent sx={{ pb: "12px !important" }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                  <Typography variant="subtitle2" fontWeight={700}>Recent Paper Trades</Typography>
                  <Chip
                    label={`${recent_trades.length} shown`}
                    size="small"
                    sx={{ fontSize: "0.65rem", height: 18 }}
                  />
                </Box>
                <RecentTradesSection items={recent_trades} />
              </CardContent>
            </Card>
          </ErrorBoundary>
        </Grid>
      </Grid>

      {/* ── Bottom row: P&L + health ─────────────────────────────────────── */}
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6}>
          <ErrorBoundary>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <PaperTradingPanel pt={paper_trading} />
              </CardContent>
            </Card>
          </ErrorBoundary>
        </Grid>
        <Grid item xs={12} sm={6}>
          <ErrorBoundary>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <SystemHealthPanel health={system_health} scanner={scanner} />
              </CardContent>
            </Card>
          </ErrorBoundary>
        </Grid>
      </Grid>
    </Box>
  );
}
