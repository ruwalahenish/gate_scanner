"use client";
import { useState } from "react";
import {
  Box, Typography, Grid, Card, CardContent, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Chip, Button, Alert, CircularProgress,
} from "@mui/material";
import { TrendingUp, TrendingDown, ShowChart, AccountBalance } from "@mui/icons-material";
import { useDispatch } from "react-redux";
import {
  useGetPortfolioSummaryQuery,
  useGetPositionsQuery,
  useGetTradesQuery,
  useSellMutation,
} from "@/store/api/portfolioApi";
import { StatCard } from "@/components/ui/StatCard";
import { PnlBadge } from "@/components/ui/PnlBadge";
import { BuyModal } from "@/components/domain/BuyModal";
import { openBuyModal } from "@/store/slices/uiSlice";
import { formatPrice, formatPct, formatIST } from "@/lib/formatters";
import { isMarketHours } from "@/lib/formatters";
import { enqueueSnackbar } from "notistack";

export default function PortfolioPage() {
  const dispatch = useDispatch();
  const [sellLoading, setSellLoading] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"positions" | "history">("positions");
  const [sell] = useSellMutation();

  const { data: summary, isLoading: sumLoading } = useGetPortfolioSummaryQuery(undefined, {
    pollingInterval: isMarketHours() ? 60_000 : 0,
  });
  const { data: positions, isLoading: posLoading } = useGetPositionsQuery(undefined, {
    pollingInterval: isMarketHours() ? 60_000 : 0,
  });
  const { data: trades } = useGetTradesQuery({ limit: 50 });

  const handleSell = async (positionId: string, symbol: string, quantity: number, price: number) => {
    setSellLoading(positionId);
    try {
      const result = await sell({
        position_id: positionId,
        quantity,
        price,
        exit_reason: "manual",
      }).unwrap();
      enqueueSnackbar(
        `Sold ${symbol}: P&L ${formatPrice(result.pnl_abs)} (${formatPct(result.pnl_pct)})`,
        { variant: result.pnl_abs >= 0 ? "success" : "error" }
      );
    } catch {
      enqueueSnackbar("Sell failed", { variant: "error" });
    } finally {
      setSellLoading(null);
    }
  };

  if (sumLoading) return <CircularProgress sx={{ m: 4 }} />;

  return (
    <Box>
      <BuyModal />

      <Typography variant="h6" fontWeight={700} mb={2}>Portfolio</Typography>

      {/* Summary Cards */}
      <Grid container spacing={2} mb={3}>
        <Grid item xs={6} sm={4} md={2}>
          <StatCard
            label="Available Capital"
            value={formatPrice(summary?.current_capital)}
            icon={<AccountBalance />}
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <StatCard
            label="Invested"
            value={formatPrice(summary?.invested_value)}
            icon={<ShowChart />}
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <StatCard
            label="Unrealized P&L"
            value={formatPrice(summary?.unrealized_pnl)}
            color={summary?.unrealized_pnl != null && summary.unrealized_pnl >= 0 ? "#22c55e" : "#ef4444"}
            icon={summary?.unrealized_pnl != null && summary.unrealized_pnl >= 0
              ? <TrendingUp /> : <TrendingDown />}
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <StatCard
            label="Realized P&L"
            value={formatPrice(summary?.realized_pnl)}
            color={summary?.realized_pnl != null && summary.realized_pnl >= 0 ? "#22c55e" : "#ef4444"}
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <StatCard
            label="Win Rate"
            value={`${summary?.win_rate?.toFixed(1) ?? "—"}%`}
            subtitle={`${summary?.winning_trades ?? 0}/${summary?.total_trades ?? 0} trades`}
            color="#6366f1"
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <StatCard
            label="Open Positions"
            value={summary?.open_positions ?? 0}
          />
        </Grid>
      </Grid>

      {/* Tab switcher */}
      <Box display="flex" gap={1} mb={2}>
        {(["positions", "history"] as const).map((tab) => (
          <Chip
            key={tab}
            label={tab === "positions" ? "Open Positions" : "Trade History"}
            onClick={() => setActiveTab(tab)}
            variant={activeTab === tab ? "filled" : "outlined"}
            color={activeTab === tab ? "primary" : "default"}
            sx={{ cursor: "pointer" }}
          />
        ))}
        <Box flex={1} />
        <Button
          size="small"
          variant="outlined"
          onClick={() => dispatch(openBuyModal(null))}
        >
          + Paper Buy
        </Button>
      </Box>

      {/* Positions table */}
      {activeTab === "positions" && (
        <TableContainer component={Paper} elevation={0} sx={{ border: "1px solid rgba(255,255,255,0.06)" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                {["Symbol", "Qty", "Avg Entry", "Current", "Unrealised P&L", "SL", "T1", "Since", "Action"].map((h) => (
                  <TableCell key={h} sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem" }}>
                    {h}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {posLoading && (
                <TableRow>
                  <TableCell colSpan={9} align="center"><CircularProgress size={24} /></TableCell>
                </TableRow>
              )}
              {(positions ?? []).map((pos) => (
                <TableRow key={pos.id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight={700} color="primary.light">
                      {pos.symbol}
                    </Typography>
                  </TableCell>
                  <TableCell>{pos.quantity}</TableCell>
                  <TableCell>{formatPrice(pos.avg_entry)}</TableCell>
                  <TableCell>{pos.current_price ? formatPrice(pos.current_price) : "—"}</TableCell>
                  <TableCell>
                    <PnlBadge pnl={pos.unrealized_pnl} pnlPct={pos.unrealized_pnl_pct} variant="body2" />
                  </TableCell>
                  <TableCell sx={{ color: "error.light" }}>{formatPrice(pos.stop_loss)}</TableCell>
                  <TableCell sx={{ color: "success.light" }}>{formatPrice(pos.t1)}</TableCell>
                  <TableCell sx={{ color: "text.secondary", fontSize: "0.75rem" }}>
                    {formatIST(pos.opened_at)}
                  </TableCell>
                  <TableCell>
                    <Button
                      size="small"
                      color="error"
                      variant="outlined"
                      disabled={sellLoading === pos.id || !pos.current_price}
                      onClick={() =>
                        handleSell(pos.id, pos.symbol, pos.quantity, pos.current_price ?? pos.avg_entry)
                      }
                    >
                      {sellLoading === pos.id ? "…" : "Sell"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {!posLoading && (positions ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} align="center" sx={{ py: 4 }}>
                    <Typography color="text.secondary">No open positions</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Trade history */}
      {activeTab === "history" && (
        <TableContainer component={Paper} elevation={0} sx={{ border: "1px solid rgba(255,255,255,0.06)" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                {["Symbol", "Side", "Qty", "Price", "P&L", "P&L %", "Reason", "Date"].map((h) => (
                  <TableCell key={h} sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem" }}>
                    {h}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {(trades?.items ?? []).map((t) => (
                <TableRow key={t.id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight={600}>{t.symbol}</Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={t.side}
                      size="small"
                      sx={{
                        height: 18, fontSize: "0.68rem",
                        bgcolor: t.side === "BUY" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                        color: t.side === "BUY" ? "success.main" : "error.main",
                      }}
                    />
                  </TableCell>
                  <TableCell>{t.quantity}</TableCell>
                  <TableCell>{formatPrice(t.price)}</TableCell>
                  <TableCell>
                    {t.pnl_abs != null
                      ? <PnlBadge pnl={t.pnl_abs} variant="body2" showAbs />
                      : "—"}
                  </TableCell>
                  <TableCell>
                    {t.pnl_pct != null
                      ? <Typography variant="body2" color={t.pnl_pct >= 0 ? "success.main" : "error.main"}>
                          {formatPct(t.pnl_pct)}
                        </Typography>
                      : "—"}
                  </TableCell>
                  <TableCell sx={{ color: "text.secondary", fontSize: "0.75rem" }}>
                    {t.exit_reason ?? "entry"}
                  </TableCell>
                  <TableCell sx={{ color: "text.secondary", fontSize: "0.75rem" }}>
                    {formatIST(t.executed_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
