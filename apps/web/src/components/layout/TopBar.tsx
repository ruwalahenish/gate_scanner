"use client";
import {
  AppBar, Toolbar, Typography, Box, LinearProgress,
  Button, Chip, CircularProgress,
} from "@mui/material";
import { PlayArrow, Refresh } from "@mui/icons-material";
import { useSelector, useDispatch } from "react-redux";
import { useTriggerScanMutation } from "@/store/api/signalsApi";
import { openScanModal } from "@/store/slices/uiSlice";
import type { RootState } from "@/store";

export function TopBar({ title }: { title?: string }) {
  const dispatch = useDispatch();
  const scanProgress = useSelector((s: RootState) => s.ws.scanProgress);
  const [triggerScan, { isLoading }] = useTriggerScanMutation();

  const handleQuickScan = async () => {
    try {
      await triggerScan({ mode: "daily" }).unwrap();
    } catch (err: unknown) {
      console.error("Scan trigger failed", err);
    }
  };

  const progressPct = scanProgress
    ? Math.round((scanProgress.done / Math.max(scanProgress.total, 1)) * 100)
    : null;

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

        {/* Scan progress indicator */}
        {scanProgress && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <CircularProgress size={16} thickness={5} />
            <Typography variant="caption" color="text.secondary">
              Scanning… {scanProgress.done}/{scanProgress.total}
            </Typography>
          </Box>
        )}

        <Button
          size="small"
          variant="contained"
          startIcon={isLoading ? <CircularProgress size={14} color="inherit" /> : <PlayArrow />}
          onClick={handleQuickScan}
          disabled={isLoading || !!scanProgress}
          sx={{ minWidth: 100 }}
        >
          {isLoading ? "Starting…" : "Run Scan"}
        </Button>
      </Toolbar>

      {/* Scan progress bar */}
      {progressPct !== null && (
        <LinearProgress
          variant="determinate"
          value={progressPct}
          sx={{ height: 2 }}
        />
      )}
    </AppBar>
  );
}
