"use client";
import {
  Box, Grid, Typography, Card, CardContent,
  Table, TableBody, TableCell, TableHead, TableRow, Chip, Alert,
} from "@mui/material";
import {
  TrendingUp, TrendingDown, AccountBalance, FlashOn,
} from "@mui/icons-material";
import Link from "next/link";
import { useMemo } from "react";
import { useSelector } from "react-redux";
import { useGetSignalsQuery, useGetScansQuery } from "@/store/api/signalsApi";
import { useGetPortfolioSummaryQuery } from "@/store/api/portfolioApi";
import { useGetAlertsQuery } from "@/store/api/alertsApi";
import { StatCard } from "@/components/ui/StatCard";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { GATEBar } from "@/components/ui/GATEBar";
import { formatPrice, formatIST, isMarketHours } from "@/lib/formatters";
import { CATEGORY_ORDER } from "@/lib/constants";
import type { RootState } from "@/store";
import type { SignalCategory } from "@/types/signal";
import type { StreamingSignal } from "@/types/scan";

export default function DashboardPage() {
  const { data: signals, isLoading: signalsLoading } = useGetSignalsQuery({ limit: 10, min_rank: 50 });
  const { data: summary } = useGetPortfolioSummaryQuery(undefined, {
    pollingInterval: isMarketHours() ? 60_000 : 0,
  });
  const { data: scans } = useGetScansQuery();
  const { data: alerts } = useGetAlertsQuery({ status: "triggered" });

  const scanProgress     = useSelector((s: RootState) => s.ws.scanProgress);
  const streamingSignals = useSelector((s: RootState) => s.ws.streamingSignals);
  const isScanning       = scanProgress !== null;

  const latestScan = scans?.[0];

  // While scanning: show streaming batch results; otherwise show authoritative DB results
  const topSignals = useMemo(() => {
    if (isScanning && streamingSignals.length > 0) {
      return [...streamingSignals]
        .sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0))
        .slice(0, 8);
    }
    return signals?.items?.slice(0, 8) ?? [];
  }, [isScanning, streamingSignals, signals]);

  const allSignals = isScanning ? streamingSignals : (signals?.items ?? []);

  const categoryCounts = useMemo(
    () =>
      CATEGORY_ORDER.reduce((acc, cat) => {
        acc[cat] = allSignals.filter((s) => s.category === cat).length;
        return acc;
      }, {} as Record<string, number>),
    [allSignals]
  );

  return (
    <Box>
      <Typography variant="h6" fontWeight={700} mb={2}>Market Overview</Typography>

      {/* P&L + portfolio strip */}
      <Grid container spacing={2} mb={3}>
        <Grid item xs={6} sm={3} md={2}>
          <StatCard
            label="Available Capital"
            value={formatPrice(summary?.current_capital)}
            icon={<AccountBalance />}
          />
        </Grid>
        <Grid item xs={6} sm={3} md={2}>
          <StatCard
            label="Unrealized P&L"
            value={formatPrice(summary?.unrealized_pnl)}
            color={summary?.unrealized_pnl != null && summary.unrealized_pnl >= 0 ? "#22c55e" : "#ef4444"}
            icon={summary?.unrealized_pnl != null && summary.unrealized_pnl >= 0
              ? <TrendingUp /> : <TrendingDown />}
          />
        </Grid>
        <Grid item xs={6} sm={3} md={2}>
          <StatCard label="Win Rate" value={`${summary?.win_rate?.toFixed(1) ?? "—"}%`} color="#6366f1" />
        </Grid>
        <Grid item xs={6} sm={3} md={2}>
          <StatCard label="Open Positions" value={summary?.open_positions ?? 0} />
        </Grid>
        {CATEGORY_ORDER.filter((c) => c !== "IGNORE").slice(0, 4).map((cat) => (
          <Grid item xs={6} sm={3} md={2} key={cat}>
            <StatCard
              label={cat}
              value={categoryCounts[cat] ?? 0}
              subtitle={isScanning ? "live" : "signals"}
              icon={<FlashOn />}
              color={cat === "INVESTMENT" ? "#22c55e" : cat === "SWING" ? "#6366f1" : undefined}
            />
          </Grid>
        ))}
      </Grid>

      {/* Scan info */}
      {isScanning && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Scan in progress — {streamingSignals.length} signals found so far
          {scanProgress && scanProgress.total > 0 &&
            ` (${scanProgress.done}/${scanProgress.total} symbols processed)`}
        </Alert>
      )}
      {!isScanning && latestScan && (
        <Alert
          severity={latestScan.status === "done" ? "info" : "warning"}
          sx={{ mb: 2 }}
        >
          Last scan: {formatIST(latestScan.triggered_at ?? null)} — {" "}
          {latestScan.signals_found ?? 0} signals found · Status: {latestScan.status}
        </Alert>
      )}

      <Grid container spacing={2}>
        {/* Top signals */}
        <Grid item xs={12} lg={7}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                {isScanning
                  ? `Live Results (${streamingSignals.length} so far)`
                  : "Top Signals (by Rank)"}
              </Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {["Symbol", "Category", "Entry", "T1", "GATE", "RR"].map((h) => (
                      <TableCell key={h} sx={{ color: "text.secondary", fontSize: "0.75rem" }}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {topSignals.map((s, idx) => {
                    const id = (s as { id?: string }).id;
                    const key = id ?? `${s.symbol}-${idx}`;
                    return (
                      <TableRow key={key} hover>
                        <TableCell>
                          <Link
                            href={`/stocks/${s.symbol}`}
                            style={{ color: "#818cf8", fontWeight: 700, textDecoration: "none" }}
                          >
                            {s.symbol}
                          </Link>
                        </TableCell>
                        <TableCell><CategoryChip category={s.category as SignalCategory} /></TableCell>
                        <TableCell>{formatPrice(s.entry)}</TableCell>
                        <TableCell sx={{ color: "success.light" }}>{formatPrice(s.t1)}</TableCell>
                        <TableCell sx={{ minWidth: 100 }}><GATEBar score={s.gate_strength} /></TableCell>
                        <TableCell>{s.rr_t1?.toFixed(1) ?? "—"}x</TableCell>
                      </TableRow>
                    );
                  })}
                  {!signalsLoading && !isScanning && topSignals.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} align="center" sx={{ py: 3 }}>
                        <Typography color="text.secondary" variant="body2">
                          No signals yet — click Run Scan to generate signals
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                  {isScanning && topSignals.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} align="center" sx={{ py: 3 }}>
                        <Typography color="text.secondary" variant="body2">
                          Waiting for first batch…
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </Grid>

        {/* Recent alerts */}
        <Grid item xs={12} lg={5}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>Recent Alerts</Typography>
              {(alerts as { id: string; symbol: string; message?: string; triggered_at?: string }[] | undefined)
                ?.slice(0, 8)
                .map((a) => (
                  <Box
                    key={a.id}
                    display="flex"
                    justifyContent="space-between"
                    alignItems="center"
                    py={0.6}
                    borderBottom="1px solid rgba(255,255,255,0.04)"
                  >
                    <Box>
                      <Typography variant="body2" fontWeight={600}>{a.symbol}</Typography>
                      <Typography variant="caption" color="text.secondary">{a.message}</Typography>
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      {formatIST(a.triggered_at ?? null)}
                    </Typography>
                  </Box>
                ))}
              {(!alerts || (alerts as unknown[]).length === 0) && (
                <Typography color="text.secondary" variant="body2">No alerts triggered</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
