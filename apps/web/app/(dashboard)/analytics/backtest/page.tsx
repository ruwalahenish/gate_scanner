"use client";
import { useState } from "react";
import {
  Box, Typography, Card, CardContent, Grid, TextField, Button,
  CircularProgress, Alert, Table, TableBody, TableCell,
  TableHead, TableRow, TableContainer, Paper,
} from "@mui/material";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { enqueueSnackbar } from "notistack";
import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { API_URL } from "@/lib/constants";
import { formatPrice, formatPct, formatIST } from "@/lib/formatters";

// Inline API calls for simplicity (backtests is low-frequency)
async function triggerBacktest(payload: object): Promise<{ backtest_id: string }> {
  const res = await fetch(`${API_URL}/api/backtests/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function fetchBacktest(id: string) {
  const res = await fetch(`${API_URL}/api/backtests/${id}`);
  return res.json();
}

async function fetchEquityCurve(id: string) {
  const res = await fetch(`${API_URL}/api/backtests/${id}/equity-curve`);
  return res.json();
}

async function fetchBtTrades(id: string) {
  const res = await fetch(`${API_URL}/api/backtests/${id}/trades`);
  return res.json();
}

export default function BacktestPage() {
  const [startDate, setStartDate] = useState("2022-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [capital, setCapital] = useState("1000000");
  const [universe, setUniverse] = useState("");
  const [running, setRunning] = useState(false);
  const [backtestId, setBacktestId] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [equityCurve, setEquityCurve] = useState<{ curve_date: string; equity: number }[]>([]);
  const [trades, setTrades] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState("");

  const handleRun = async () => {
    setError("");
    setRunning(true);
    setResult(null);
    try {
      const universeList = universe.trim()
        ? universe.split(",").map((s) => s.trim().toUpperCase())
        : [];
      const { backtest_id } = await triggerBacktest({
        start_date: startDate,
        end_date: endDate,
        initial_capital: parseFloat(capital),
        universe: universeList,
      });
      setBacktestId(backtest_id);
      enqueueSnackbar("Backtest started — polling for results…", { variant: "info" });

      // Poll every 5s for up to 10 minutes
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        const bt = await fetchBacktest(backtest_id);
        if (bt.status === "done") {
          clearInterval(poll);
          setResult(bt);
          const [curve, trs] = await Promise.all([
            fetchEquityCurve(backtest_id),
            fetchBtTrades(backtest_id),
          ]);
          setEquityCurve(curve);
          setTrades(trs);
          setRunning(false);
        } else if (bt.status === "failed" || attempts > 120) {
          clearInterval(poll);
          setError(bt.error_message ?? "Backtest failed or timed out");
          setRunning(false);
        }
      }, 5000);
    } catch (err: unknown) {
      setError(String(err));
      setRunning(false);
    }
  };

  return (
    <Box>
      <Typography variant="h6" fontWeight={700} mb={2}>Backtest Runner</Typography>

      {/* Config form */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="flex-end">
            <Grid item xs={6} sm={3}>
              <TextField
                label="Start Date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                fullWidth
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <TextField
                label="End Date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                fullWidth
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={6} sm={2}>
              <TextField
                label="Capital (₹)"
                type="number"
                value={capital}
                onChange={(e) => setCapital(e.target.value)}
                fullWidth
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <TextField
                label="Universe (comma-separated, or leave blank for default)"
                value={universe}
                onChange={(e) => setUniverse(e.target.value)}
                placeholder="RELIANCE,TCS,HDFCBANK"
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={1}>
              <Button
                variant="contained"
                fullWidth
                onClick={handleRun}
                disabled={running}
                sx={{ height: 40 }}
              >
                {running ? <CircularProgress size={20} color="inherit" /> : "Run"}
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {running && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Backtest running… This may take 2–5 minutes for full universe.
        </Alert>
      )}

      {/* Results */}
      {result && (
        <>
          <Grid container spacing={2} mb={3}>
            {[
              ["Final Equity", formatPrice(result.final_equity as number)],
              ["Total Trades", result.total_trades],
              ["Win Rate", `${((result.win_rate as number) * 100).toFixed(1)}%`],
              ["CAGR", `${((result.cagr as number) * 100).toFixed(2)}%`],
              ["Sharpe", (result.sharpe_ratio as number)?.toFixed(2)],
              ["Max Drawdown", `${((result.max_drawdown as number) * 100).toFixed(1)}%`],
            ].map(([label, value]) => (
              <Grid item xs={6} sm={2} key={String(label)}>
                <Card>
                  <CardContent sx={{ py: 1 }}>
                    <Typography variant="caption" color="text.secondary">{label}</Typography>
                    <Typography variant="h6" fontWeight={700}>{String(value ?? "—")}</Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>

          {/* Equity curve */}
          {equityCurve.length > 0 && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>Equity Curve</Typography>
                <ResponsiveContainer width="100%" height={250}>
                  <AreaChart data={equityCurve}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="curve_date" stroke="#94a3b8" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#1a1a24", border: "1px solid rgba(255,255,255,0.1)" }}
                      formatter={(v: number) => [formatPrice(v), "Equity"]}
                    />
                    <Area
                      type="monotone"
                      dataKey="equity"
                      stroke="#6366f1"
                      fill="rgba(99,102,241,0.15)"
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Trade list */}
          {trades.length > 0 && (
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>Trades ({trades.length})</Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        {["Symbol", "Entry Date", "Exit Date", "Entry ₹", "Exit ₹", "P&L", "P&L %", "Reason"].map((h) => (
                          <TableCell key={h} sx={{ color: "text.secondary", fontSize: "0.75rem" }}>{h}</TableCell>
                        ))}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {trades.slice(0, 100).map((t) => (
                        <TableRow key={String(t.id)} hover>
                          <TableCell fontWeight={600}>{String(t.symbol)}</TableCell>
                          <TableCell sx={{ fontSize: "0.75rem" }}>{String(t.entry_date)}</TableCell>
                          <TableCell sx={{ fontSize: "0.75rem" }}>{String(t.exit_date ?? "—")}</TableCell>
                          <TableCell>{formatPrice(t.entry_price as number)}</TableCell>
                          <TableCell>{formatPrice(t.exit_price as number | null)}</TableCell>
                          <TableCell>
                            <Typography
                              variant="body2"
                              color={(t.pnl_abs as number) >= 0 ? "success.main" : "error.main"}
                            >
                              {formatPrice(t.pnl_abs as number | null)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography
                              variant="body2"
                              color={(t.pnl_pct as number) >= 0 ? "success.main" : "error.main"}
                            >
                              {formatPct((t.pnl_pct as number | null))}
                            </Typography>
                          </TableCell>
                          <TableCell sx={{ color: "text.secondary", fontSize: "0.75rem" }}>
                            {String(t.exit_reason ?? "—")}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </Box>
  );
}
