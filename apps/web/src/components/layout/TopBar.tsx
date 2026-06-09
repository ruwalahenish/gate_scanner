"use client";
import {
  AppBar, Toolbar, Typography, Box, LinearProgress,
  CircularProgress,
} from "@mui/material";
import { useSelector, useDispatch } from "react-redux";
import { useEffect } from "react";
import { useGetScanStatusQuery } from "@/store/api/scannerApi";
import { scanCompleted, scanFailed } from "@/store/slices/wsSlice";
import { scannerApi } from "@/store/api/scannerApi";
import { stockMasterApi } from "@/store/api/stockMasterApi";
import type { RootState, AppDispatch } from "@/store";

export function TopBar({ title }: { title?: string }) {
  const dispatch = useDispatch<AppDispatch>();
  const scanProgress   = useSelector((s: RootState) => s.ws.scanProgress);
  const currentScanId  = useSelector((s: RootState) => s.ws.currentScanId);
  const streamingCount = useSelector((s: RootState) => s.ws.streamingSignals.length);

  // Polling fallback — if WS misses scan.complete/failed, polling catches it
  const { data: pollData } = useGetScanStatusQuery(currentScanId!, {
    skip: !currentScanId,
    pollingInterval: 5000,
  });

  useEffect(() => {
    if (!pollData || !currentScanId) return;
    if (pollData.status === "done") {
      dispatch(scanCompleted({ scan_id: currentScanId, signals_count: pollData.signals_found ?? 0 }));
      dispatch(scannerApi.util.invalidateTags(["Signal", "Scan", "Dashboard"]));
      dispatch(stockMasterApi.util.invalidateTags(["Stock"]));
    } else if (pollData.status === "failed") {
      dispatch(scanFailed());
    }
  }, [pollData, currentScanId, dispatch]);

  const hasRealProgress = scanProgress !== null && scanProgress.total > 0;
  const progressPct = hasRealProgress
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

        {/* Scan in-progress indicator */}
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
      </Toolbar>

      {/* Progress bar */}
      {scanProgress && (
        <LinearProgress
          variant={hasRealProgress ? "determinate" : "indeterminate"}
          value={hasRealProgress ? progressPct : undefined}
          sx={{ height: 2 }}
        />
      )}
    </AppBar>
  );
}

