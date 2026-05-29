"use client";
import { useState } from "react";
import {
  Box, Typography, Grid, Card, CardContent, Chip,
  CircularProgress, Alert, FormControl, InputLabel, Select, MenuItem,
  Table, TableBody, TableCell, TableHead, TableRow, Divider, Button,
} from "@mui/material";
import { ArrowBack } from "@mui/icons-material";
import { useParams, useRouter } from "next/navigation";
import { useDispatch } from "react-redux";
import { GATEChart } from "@/components/domain/GATEChart";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { GATEBar } from "@/components/ui/GATEBar";
import { useGetChartDataQuery, useGetSymbolAnalysisQuery, useGetSignalHistoryQuery } from "@/store/api/signalsApi";
import { openBuyModal } from "@/store/slices/uiSlice";
import { BuyModal } from "@/components/domain/BuyModal";
import { formatPrice, formatRR, formatScore, formatIST } from "@/lib/formatters";
import { TIMEFRAME_LABELS } from "@/lib/constants";
import type { SignalCategory } from "@/types/signal";

const TIMEFRAMES = ["1d", "1wk", "1mo", "60m", "4h"];

export default function SymbolDetailPage() {
  const params = useParams();
  const router = useRouter();
  const dispatch = useDispatch();
  const symbol = (params.symbol as string).toUpperCase();
  const [tf, setTf] = useState("1d");

  const { data: chartData, isLoading: chartLoading } = useGetChartDataQuery({ symbol, timeframe: tf });
  const { data: analysis, isLoading: analysisLoading } = useGetSymbolAnalysisQuery(symbol);
  const { data: history } = useGetSignalHistoryQuery({ symbol, limit: 10 });

  const latestSignal = history?.[0];
  const signal = (analysis as { signal?: Record<string, unknown> } | null)?.signal;
  const perTf = (analysis as { per_tf?: Record<string, Record<string, unknown>> } | null)?.per_tf ?? {};

  return (
    <Box>
      <BuyModal />

      <Box display="flex" alignItems="center" gap={1} mb={2}>
        <Button size="small" startIcon={<ArrowBack />} onClick={() => router.back()}>
          Back
        </Button>
        <Typography variant="h6" fontWeight={700}>{symbol}</Typography>
        {latestSignal && <CategoryChip category={latestSignal.category as SignalCategory} />}
        <Box flex={1} />
        <Button
          variant="contained"
          size="small"
          color="success"
          onClick={() => dispatch(openBuyModal(symbol))}
        >
          Paper Buy
        </Button>
      </Box>

      <Grid container spacing={2}>
        {/* Chart column */}
        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent sx={{ pb: "8px !important" }}>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                <Typography variant="subtitle2" color="text.secondary">
                  Candlestick Chart with EMA Stack
                </Typography>
                <FormControl size="small" sx={{ minWidth: 90 }}>
                  <Select value={tf} onChange={(e) => setTf(e.target.value as string)}>
                    {TIMEFRAMES.map((t) => (
                      <MenuItem key={t} value={t}>{TIMEFRAME_LABELS[t] ?? t}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>
              <GATEChart
                bars={(chartData?.bars as Parameters<typeof GATEChart>[0]["bars"]) ?? []}
                signal={signal as Parameters<typeof GATEChart>[0]["signal"]}
                loading={chartLoading}
              />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: "block" }}>
                Purple lines = EMA 20/50/100/200 · Blue = Entry · Green = T1/T2/T3 · Red = SL
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Signal detail column */}
        <Grid item xs={12} lg={4}>
          {analysisLoading ? (
            <Box display="flex" justifyContent="center" pt={4}><CircularProgress /></Box>
          ) : (
            <Box display="flex" flexDirection="column" gap={2}>
              {/* Latest signal levels */}
              {latestSignal && (
                <Card>
                  <CardContent>
                    <Typography variant="subtitle2" gutterBottom>Signal Levels</Typography>
                    {[
                      ["Entry",    latestSignal.entry,     "primary.main"],
                      ["Stop Loss",latestSignal.stop_loss, "error.main"],
                      ["T1",       latestSignal.t1,        "success.light"],
                      ["T2",       latestSignal.t2,        "success.main"],
                      ["T3",       latestSignal.t3,        "success.dark"],
                    ].map(([label, val, color]) => (
                      <Box key={String(label)} display="flex" justifyContent="space-between" mb={0.5}>
                        <Typography variant="caption" color="text.secondary">{label}</Typography>
                        <Typography variant="caption" fontWeight={700} sx={{ color: color as string }}>
                          {formatPrice(val as number | null)}
                        </Typography>
                      </Box>
                    ))}
                    <Divider sx={{ my: 1 }} />
                    {[
                      ["RR T1", formatRR(latestSignal.rr_t1)],
                      ["RR T2", formatRR(latestSignal.rr_t2)],
                    ].map(([k, v]) => (
                      <Box key={String(k)} display="flex" justifyContent="space-between">
                        <Typography variant="caption" color="text.secondary">{k}</Typography>
                        <Typography variant="caption" fontWeight={600}>{v}</Typography>
                      </Box>
                    ))}
                  </CardContent>
                </Card>
              )}

              {/* MTF heatmap */}
              <Card>
                <CardContent>
                  <Typography variant="subtitle2" gutterBottom>MTF GATE Scores</Typography>
                  {Object.entries(perTf).map(([timeframe, tfData]) => {
                    const gate = (tfData.gate as { score?: number } | null)?.score;
                    const ema = (tfData.ema as { stack?: string } | null)?.stack;
                    return (
                      <Box key={timeframe} display="flex" alignItems="center" gap={1} mb={0.8}>
                        <Typography variant="caption" color="text.secondary" sx={{ minWidth: 36 }}>
                          {timeframe}
                        </Typography>
                        <GATEBar score={gate ?? null} />
                        <Chip
                          label={ema ?? "—"}
                          size="small"
                          sx={{
                            height: 16, fontSize: "0.6rem",
                            bgcolor: ema === "bullish" ? "rgba(34,197,94,0.15)"
                              : ema === "bearish" ? "rgba(239,68,68,0.15)"
                              : "rgba(255,255,255,0.06)",
                            color: ema === "bullish" ? "success.main"
                              : ema === "bearish" ? "error.main"
                              : "text.secondary",
                          }}
                        />
                      </Box>
                    );
                  })}
                </CardContent>
              </Card>
            </Box>
          )}
        </Grid>

        {/* Signal history */}
        {history && history.length > 0 && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>Signal History</Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      {["Date", "Category", "Entry", "GATE", "Confidence", "Phase"].map((h) => (
                        <TableCell key={h} sx={{ color: "text.secondary", fontSize: "0.75rem" }}>{h}</TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {history.map((s) => (
                      <TableRow key={s.id} hover>
                        <TableCell sx={{ fontSize: "0.75rem" }}>{formatIST(s.created_at)}</TableCell>
                        <TableCell><CategoryChip category={s.category as SignalCategory} /></TableCell>
                        <TableCell>{formatPrice(s.entry)}</TableCell>
                        <TableCell><GATEBar score={s.gate_strength} showLabel /></TableCell>
                        <TableCell>{formatScore(s.confidence)}</TableCell>
                        <TableCell sx={{ color: "text.secondary", fontSize: "0.75rem" }}>{s.phase}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}
