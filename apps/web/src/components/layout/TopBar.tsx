"use client";
import {
  AppBar, Toolbar, Typography, Box, LinearProgress,
  Button, CircularProgress, IconButton, Tooltip,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField,
} from "@mui/material";
import { PlayArrow, AccountBalanceWallet, Edit } from "@mui/icons-material";
import { useSelector, useDispatch } from "react-redux";
import { useEffect, useState } from "react";
import { useTriggerScanMutation, useGetScanStatusQuery, signalsApi } from "@/store/api/signalsApi";
import { useGetPortfolioSummaryQuery, useUpdateCapitalMutation } from "@/store/api/portfolioApi";
import { scanStarted, scanCompleted, scanFailed } from "@/store/slices/wsSlice";
import type { RootState } from "@/store";
import type { AppDispatch } from "@/store";
import type { ScanResult } from "@/types/scan";

export function TopBar({ title }: { title?: string }) {
  const dispatch = useDispatch<AppDispatch>();
  const scanProgress      = useSelector((s: RootState) => s.ws.scanProgress);
  const currentScanId     = useSelector((s: RootState) => s.ws.currentScanId);
  const streamingCount    = useSelector((s: RootState) => s.ws.streamingSignals.length);
  const [triggerScan, { isLoading }] = useTriggerScanMutation();

  // ── Capital edit state ────────────────────────────────────────────────
  const { data: summary } = useGetPortfolioSummaryQuery();
  const [updateCapital, { isLoading: isUpdatingCapital }] = useUpdateCapitalMutation();
  const [capitalDialogOpen, setCapitalDialogOpen] = useState(false);
  const [capitalInput, setCapitalInput] = useState("");

  // ── Polling fallback ─────────────────────────────────────────────────
  // If the WebSocket misses scan.complete / scan.failed (e.g. reconnect),
  // we poll the status endpoint every 5 s while a scan is in flight.
  const { data: pollData } = useGetScanStatusQuery(currentScanId!, {
    skip: !currentScanId,
    pollingInterval: 5000,
  });

  useEffect(() => {
    if (!pollData || !currentScanId) return;
    const status = pollData.status;
    if (status === "done") {
      dispatch(scanCompleted(currentScanId));
      dispatch(signalsApi.util.invalidateTags(["Signal", "Scan"]));
    } else if (status === "failed") {
      dispatch(scanFailed());
    }
  }, [pollData, currentScanId, dispatch]);

  // ── Trigger handler ───────────────────────────────────────────────────
  const handleQuickScan = async () => {
    try {
      const { scan_id } = await triggerScan({ mode: "daily" }).unwrap();
      // Immediately disable the button and start polling — before the WS event arrives.
      dispatch(scanStarted(scan_id));
    } catch (err: unknown) {
      console.error("Scan trigger failed", err);
    }
  };

  const handleOpenCapitalDialog = () => {
    setCapitalInput(String(summary?.current_capital ?? ""));
    setCapitalDialogOpen(true);
  };

  const handleSaveCapital = async () => {
    const amount = parseFloat(capitalInput);
    if (!isNaN(amount) && amount > 0) {
      await updateCapital({ amount });
    }
    setCapitalDialogOpen(false);
  };

  // ── Progress display helpers ──────────────────────────────────────────
  const hasRealProgress = scanProgress !== null && scanProgress.total > 0;
  // Guard against division by zero: only compute % when total > 0
  const progressPct     = hasRealProgress
    ? Math.min(100, Math.round((scanProgress.done / scanProgress.total) * 100))
    : 0;

  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{
        bgcolor: "background.paper",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        color: "text.primary",
      }}
    >
      <Toolbar sx={{ minHeight: 56, gap: 2 }}>
        <Typography variant="subtitle1" fontWeight={600} sx={{ flex: 1 }}>
          {title ?? "GATE Platform"}
        </Typography>

        {/* Available capital display */}
        <Tooltip title="Available capital — click to update">
          <Box
            onClick={handleOpenCapitalDialog}
            sx={{
              display: "flex", alignItems: "center", gap: 0.5,
              cursor: "pointer", px: 1.5, py: 0.5, borderRadius: 1,
              bgcolor: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.08)",
              "&:hover": { bgcolor: "rgba(255,255,255,0.08)" },
            }}
          >
            <AccountBalanceWallet sx={{ fontSize: 15, color: "text.secondary" }} />
            <Typography variant="caption" color="text.secondary" sx={{ userSelect: "none" }}>
              Available:
            </Typography>
            <Typography variant="caption" fontWeight={600} color="success.main" sx={{ userSelect: "none" }}>
              {summary?.current_capital != null
                ? `₹${summary.current_capital.toLocaleString("en-IN")}`
                : "—"}
            </Typography>
            <Edit sx={{ fontSize: 12, color: "text.disabled", ml: 0.25 }} />
          </Box>
        </Tooltip>

        {/* In-progress indicator */}
        {scanProgress && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <CircularProgress size={16} thickness={5} />
            <Typography variant="caption" color="text.secondary">
              {hasRealProgress
                ? `Scanning… ${scanProgress.done}/${scanProgress.total} (${progressPct}%)`
                : "Scanning…"}
              {streamingCount > 0 && ` · ${streamingCount} signals`}
            </Typography>
          </Box>
        )}

        <Button
          size="small"
          variant="contained"
          startIcon={
            isLoading
              ? <CircularProgress size={14} color="inherit" />
              : <PlayArrow />
          }
          onClick={handleQuickScan}
          disabled={isLoading || !!scanProgress}
          sx={{ minWidth: 100 }}
        >
          {isLoading ? "Starting…" : "Run Scan"}
        </Button>
      </Toolbar>

      {/* Progress bar — indeterminate until we get real progress data */}
      {scanProgress && (
        <LinearProgress
          variant={hasRealProgress ? "determinate" : "indeterminate"}
          value={hasRealProgress ? progressPct : undefined}
          sx={{ height: 2 }}
        />
      )}

      {/* Capital edit dialog */}
      <Dialog open={capitalDialogOpen} onClose={() => setCapitalDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Update Available Capital</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            label="Amount (INR)"
            type="number"
            value={capitalInput}
            onChange={(e) => setCapitalInput(e.target.value)}
            inputProps={{ min: 1, step: 100 }}
            sx={{ mt: 1 }}
            helperText="Sets both initial and current capital for a fresh start"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCapitalDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSaveCapital}
            disabled={isUpdatingCapital || !capitalInput || parseFloat(capitalInput) <= 0}
          >
            {isUpdatingCapital ? <CircularProgress size={16} color="inherit" /> : "Save"}
          </Button>
        </DialogActions>
      </Dialog>
    </AppBar>
  );
}
