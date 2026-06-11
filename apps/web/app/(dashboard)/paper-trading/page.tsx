"use client";
import { useState, useCallback, memo } from "react";
import {
  Box, Card, CardContent, Typography, Chip, Tab, Tabs,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Select, MenuItem, TextField, FormControl, InputLabel,
  CircularProgress, Skeleton, Divider, Stack, Tooltip,
} from "@mui/material";
import { TrendingUp, TrendingDown, SellOutlined, InfoOutlined } from "@mui/icons-material";
import { enqueueSnackbar } from "notistack";
import {
  useGetPerformanceQuery,
  useGetPositionsQuery,
  useGetTradesQuery,
  useSellPositionMutation,
} from "@/store/api/paperTradingApi";
import { EmptyState } from "@/components/ui/EmptyState";
import { StockLink } from "@/components/ui/StockLink";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { formatPrice, formatPct, formatIST } from "@/lib/formatters";
import { STATUS_COLORS, EXIT_LABEL } from "@/lib/constants";
import type { Position, Trade } from "@/types/paper_trading";

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const EXIT_REASON_OPTIONS = Object.entries(EXIT_LABEL).map(([value, label]) => ({ value, label }));

// ─────────────────────────────────────────────────────────────────────────────
// Module-level constants
// ─────────────────────────────────────────────────────────────────────────────

const SIDE_CHIP_SX = {
  BUY: {
    fontSize: "0.62rem", height: 18,
    bgcolor: `${STATUS_COLORS.INVESTMENT}1e`,
    color: "success.main",
  },
  SELL: {
    fontSize: "0.62rem", height: 18,
    bgcolor: "rgba(239,68,68,0.12)",
    color: "error.main",
  },
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Performance bar
// ─────────────────────────────────────────────────────────────────────────────

const MetricPill = memo(function MetricPill({
  label, value, color,
}: { label: string; value: string; color?: string }) {
  return (
    <Box textAlign="center" sx={{ minWidth: 80 }}>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: "0.68rem", mb: 0.2 }}>
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={700} sx={{ color: color ?? "text.primary" }}>
        {value}
      </Typography>
    </Box>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Sell dialog
// ─────────────────────────────────────────────────────────────────────────────

function SellDialog({
  position,
  onClose,
}: {
  position: Position | null;
  onClose: () => void;
}) {
  const [price, setPrice]           = useState("");
  const [exitReason, setExitReason] = useState("manual");
  const [sellPosition, { isLoading }] = useSellPositionMutation();

  if (!position) return null;

  const handleConfirm = async () => {
    const p = parseFloat(price);
    if (!p || p <= 0) {
      enqueueSnackbar("Enter a valid price", { variant: "warning" });
      return;
    }
    try {
      await sellPosition({
        position_id: position.id,
        quantity:    position.quantity,
        price:       p,
        exit_reason: exitReason,
      }).unwrap();
      enqueueSnackbar(`${position.symbol} sold at ${formatPrice(p)}`, { variant: "success" });
      onClose();
    } catch (_err) {
      enqueueSnackbar("Sell failed — check logs", { variant: "error" });
    }
  };

  const estPnl = price
    ? (parseFloat(price) - position.avg_entry) * position.quantity
    : null;

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth aria-label="Sell position">
      <DialogTitle sx={{ pb: 1 }}>
        Sell {position.symbol}
        <Typography variant="caption" color="text.secondary" display="block">
          {position.quantity} shares · avg entry {formatPrice(position.avg_entry)}
        </Typography>
      </DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          fullWidth
          label="Exit Price (₹)"
          type="number"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          inputProps={{ min: 0.01, step: 0.05 }}
          sx={{ mb: 2, mt: 0.5 }}
          helperText={
            estPnl != null
              ? `Est. P&L: ${estPnl >= 0 ? "+" : ""}${formatPrice(estPnl, 0)}`
              : "Enter price to see estimated P&L"
          }
          FormHelperTextProps={{
            sx: { color: estPnl != null ? (estPnl >= 0 ? "success.main" : "error.main") : "text.disabled" },
          }}
        />
        <FormControl fullWidth size="small">
          <InputLabel>Exit Reason</InputLabel>
          <Select
            value={exitReason}
            label="Exit Reason"
            onChange={(e) => setExitReason(e.target.value)}
          >
            {EXIT_REASON_OPTIONS.map((o) => (
              <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={isLoading}>Cancel</Button>
        <Button
          variant="contained"
          color="error"
          onClick={handleConfirm}
          disabled={isLoading || !price || parseFloat(price) <= 0}
          startIcon={isLoading ? <CircularProgress size={14} color="inherit" /> : <SellOutlined />}
        >
          {isLoading ? "Selling…" : "Confirm Sell"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Open positions tab
// ─────────────────────────────────────────────────────────────────────────────

function OpenPositionsTab({ onSell }: { onSell: (pos: Position) => void }) {
  const { data: positions, isLoading } = useGetPositionsQuery();

  if (isLoading) {
    return <Box p={2}><SkeletonCard rows={4} /></Box>;
  }

  if (!positions || positions.length === 0) {
    return (
      <EmptyState
        icon={<TrendingUp />}
        title="No open positions"
        description="Positions are created automatically when BUY signals exceed the rank threshold"
      />
    );
  }

  return (
    <TableContainer aria-label="Open positions">
      <Table size="small">
        <TableHead>
          <TableRow>
            {["Symbol", "Qty", "Avg Entry", "Current", "Unrealized P&L", "SL", "T1", "Source", "Action"].map((h) => (
              <TableCell key={h} sx={{ color: "text.secondary", fontSize: "0.72rem", whiteSpace: "nowrap" }}>
                {h}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {positions.map((pos) => {
            const unreal  = pos.unrealized_pnl ?? 0;
            const unrPct  = pos.unrealized_pnl_pct ?? 0;
            const isUp    = unreal >= 0;

            return (
              <TableRow key={pos.id} hover>
                <TableCell>
                  <Box>
                    <StockLink symbol={pos.symbol} variant="body2" fontWeight={700} />
                    {pos.auto_created && (
                      <Chip label="Auto" size="small" sx={{ fontSize: "0.6rem", height: 16, mt: 0.2 }} />
                    )}
                  </Box>
                </TableCell>
                <TableCell sx={{ fontSize: "0.78rem" }}>{pos.quantity}</TableCell>
                <TableCell sx={{ fontSize: "0.78rem" }}>{formatPrice(pos.avg_entry)}</TableCell>
                <TableCell sx={{ fontSize: "0.78rem" }}>
                  {pos.current_price != null ? formatPrice(pos.current_price) : "—"}
                </TableCell>
                <TableCell>
                  {pos.current_price != null ? (
                    <Box display="flex" alignItems="center" gap={0.5}>
                      {isUp
                        ? <TrendingUp sx={{ fontSize: 14, color: "success.main" }} />
                        : <TrendingDown sx={{ fontSize: 14, color: "error.main" }} />}
                      <Typography
                        variant="body2"
                        fontWeight={600}
                        color={isUp ? "success.main" : "error.main"}
                        sx={{ fontSize: "0.78rem" }}
                      >
                        {isUp ? "+" : ""}{formatPrice(unreal, 0)} ({formatPct(unrPct)})
                      </Typography>
                    </Box>
                  ) : (
                    <Typography variant="caption" color="text.disabled">—</Typography>
                  )}
                </TableCell>
                <TableCell sx={{ fontSize: "0.75rem", color: "error.light" }}>
                  {pos.stop_loss != null ? formatPrice(pos.stop_loss) : "—"}
                </TableCell>
                <TableCell sx={{ fontSize: "0.75rem", color: "success.light" }}>
                  {pos.t1 != null ? formatPrice(pos.t1) : "—"}
                </TableCell>
                <TableCell>
                  <Chip
                    label={pos.creation_source === "scanner_auto" ? "Scanner" : "Manual"}
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: "0.6rem", height: 18 }}
                  />
                </TableCell>
                <TableCell>
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    onClick={() => onSell(pos)}
                    sx={{ fontSize: "0.7rem", py: 0.3, minWidth: 50 }}
                  >
                    Sell
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Trade history tab
// ─────────────────────────────────────────────────────────────────────────────

function TradeHistoryTab() {
  const [page] = useState(0);
  const PAGE_SIZE = 50;
  const { data, isLoading } = useGetTradesQuery({ limit: PAGE_SIZE, offset: page * PAGE_SIZE });

  if (isLoading) {
    return <Box p={2}><SkeletonCard rows={5} /></Box>;
  }

  const trades = data?.items ?? [];

  if (trades.length === 0) {
    return (
      <EmptyState
        title="No closed trades yet"
        description="Trades appear here once positions are exited"
      />
    );
  }

  return (
    <TableContainer aria-label="Trade history">
      <Table size="small">
        <TableHead>
          <TableRow>
            {["Symbol", "Side", "Qty", "Price ₹", "P&L", "P&L %", "Exit Reason", "Date"].map((h) => (
              <TableCell key={h} sx={{ color: "text.secondary", fontSize: "0.72rem", whiteSpace: "nowrap" }}>
                {h}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {trades.map((t: Trade) => {
            const isWin = (t.pnl_abs ?? 0) >= 0;
            const pnlColor = isWin ? "success.main" : "error.main";
            return (
              <TableRow key={t.id} hover>
                <TableCell sx={{ fontSize: "0.8rem" }}>
                  <StockLink symbol={t.symbol} variant="body2" fontWeight={700} />
                </TableCell>
                <TableCell>
                  <Chip
                    label={t.side}
                    size="small"
                    sx={t.side === "BUY" ? SIDE_CHIP_SX.BUY : SIDE_CHIP_SX.SELL}
                  />
                </TableCell>
                <TableCell sx={{ fontSize: "0.75rem" }}>{t.quantity}</TableCell>
                <TableCell sx={{ fontSize: "0.75rem" }}>{formatPrice(t.price)}</TableCell>
                <TableCell>
                  {t.pnl_abs != null ? (
                    <Typography variant="inherit" fontSize="0.78rem" fontWeight={600} color={pnlColor}>
                      {isWin ? "+" : ""}{formatPrice(t.pnl_abs, 0)}
                    </Typography>
                  ) : "—"}
                </TableCell>
                <TableCell>
                  {t.pnl_pct != null ? (
                    <Typography variant="inherit" fontSize="0.75rem" color={pnlColor}>
                      {formatPct(t.pnl_pct * 100)}
                    </Typography>
                  ) : "—"}
                </TableCell>
                <TableCell sx={{ fontSize: "0.72rem", color: "text.secondary" }}>
                  {EXIT_LABEL[t.exit_reason ?? ""] ?? t.exit_reason ?? "—"}
                </TableCell>
                <TableCell sx={{ fontSize: "0.7rem", color: "text.secondary", whiteSpace: "nowrap" }}>
                  {formatIST(t.executed_at)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

export default function PaperTradingPage() {
  const [activeTab, setActiveTab]     = useState<"positions" | "history">("positions");
  const [sellTarget, setSellTarget]   = useState<Position | null>(null);

  const { data: perf, isLoading: perfLoading } = useGetPerformanceQuery();

  return (
    <Box>
      {/* Header */}
      <Box display="flex" alignItems="baseline" gap={1} mb={2}>
        <Typography variant="h6" fontWeight={700}>Paper Trading</Typography>
        <Tooltip title="All positions are created automatically from GATE Scanner BUY signals" placement="right">
          <InfoOutlined sx={{ fontSize: 15, color: "text.disabled", cursor: "help" }} />
        </Tooltip>
      </Box>

      {/* ── Performance bar ───────────────────────────────────────────────── */}
      <Card sx={{ mb: 2 }}>
        <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
          {perfLoading ? (
            <Box display="flex" gap={3}>
              {[1,2,3,4,5].map((i) => <Skeleton key={i} width={80} height={40} />)}
            </Box>
          ) : perf ? (
            <>
              <Stack direction="row" spacing={0} divider={<Divider orientation="vertical" flexItem />}
                flexWrap="wrap" useFlexGap sx={{ gap: 1.5 }}>
                <MetricPill
                  label="Total P&L"
                  value={`${perf.total_pnl >= 0 ? "+" : ""}${formatPrice(perf.total_pnl, 0)}`}
                  color={perf.total_pnl >= 0 ? STATUS_COLORS.INVESTMENT : "error.main"}
                />
                <MetricPill
                  label="Realized"
                  value={`${perf.realized_pnl >= 0 ? "+" : ""}${formatPrice(perf.realized_pnl, 0)}`}
                  color={perf.realized_pnl >= 0 ? STATUS_COLORS.INVESTMENT : "error.main"}
                />
                <MetricPill
                  label="Unrealized"
                  value={`${perf.unrealized_pnl >= 0 ? "+" : ""}${formatPrice(perf.unrealized_pnl, 0)}`}
                  color={perf.unrealized_pnl >= 0 ? STATUS_COLORS.INVESTMENT : "error.main"}
                />
                <MetricPill
                  label="Win Rate"
                  value={`${perf.win_rate.toFixed(1)}%`}
                  color={perf.win_rate >= 50 ? STATUS_COLORS.INVESTMENT : "error.main"}
                />
                <MetricPill
                  label="Open Positions"
                  value={String(perf.open_positions)}
                />
                <MetricPill
                  label="Total Trades"
                  value={String(perf.total_trades)}
                />
                <MetricPill
                  label="Avg Win"
                  value={perf.avg_win_pct !== 0 ? `+${perf.avg_win_pct.toFixed(1)}%` : "—"}
                  color={STATUS_COLORS.INVESTMENT}
                />
                <MetricPill
                  label="Avg Loss"
                  value={perf.avg_loss_pct !== 0 ? `${perf.avg_loss_pct.toFixed(1)}%` : "—"}
                  color="error.main"
                />
                <MetricPill
                  label="Capital"
                  value={formatPrice(perf.current_capital, 0)}
                />
              </Stack>
            </>
          ) : (
            <Typography variant="body2" color="text.secondary">No trades recorded yet.</Typography>
          )}
        </CardContent>
      </Card>

      {/* ── Tabs + table ──────────────────────────────────────────────────── */}
      <Card>
        <Box sx={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <Tabs
            value={activeTab}
            onChange={(_, v) => setActiveTab(v)}
            sx={{ minHeight: 42, "& .MuiTab-root": { minHeight: 42, fontSize: "0.8rem" } }}
          >
            <Tab value="positions" label="Open Positions" />
            <Tab value="history"   label="Trade History"  />
          </Tabs>
        </Box>

        {activeTab === "positions" ? (
          <OpenPositionsTab onSell={setSellTarget} />
        ) : (
          <TradeHistoryTab />
        )}
      </Card>

      {/* Sell dialog */}
      {sellTarget && (
        <SellDialog position={sellTarget} onClose={() => setSellTarget(null)} />
      )}
    </Box>
  );
}
