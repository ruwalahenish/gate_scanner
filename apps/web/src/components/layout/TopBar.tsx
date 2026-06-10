"use client";
import {
  AppBar, Toolbar, Typography, Box, LinearProgress,
  CircularProgress, IconButton,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import { useSelector, useDispatch } from "react-redux";
import { useEffect } from "react";
import { useGetScanStatusQuery } from "@/store/api/scannerApi";
import { scanCompleted, scanFailed } from "@/store/slices/wsSlice";
import { scannerApi } from "@/store/api/scannerApi";
import { stockMasterApi } from "@/store/api/stockMasterApi";
import type { AppDispatch } from "@/store";
import {
  selectScanProgress,
  selectCurrentScanId,
  selectStreamingCount,
  selectWsConnected,
  selectHasRealProgress,
  selectScanProgressPct,
} from "@/store/selectors";

interface TopBarProps {
  title?: string;
  onMenuClick?: () => void;
}

export function TopBar({ title, onMenuClick }: TopBarProps) {
  const dispatch = useDispatch<AppDispatch>();

  const scanProgress    = useSelector(selectScanProgress);
  const currentScanId   = useSelector(selectCurrentScanId);
  const streamingCount  = useSelector(selectStreamingCount);
  const wsConnected     = useSelector(selectWsConnected);
  const hasRealProgress = useSelector(selectHasRealProgress);
  const progressPct     = useSelector(selectScanProgressPct);

  // Polling fallback — only active when WS is disconnected to avoid redundant requests.
  const { data: pollData } = useGetScanStatusQuery(currentScanId!, {
    skip: !currentScanId || wsConnected,
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
      <Toolbar sx={{ minHeight: 56, gap: 1 }}>
        {/* Hamburger — only visible on mobile/tablet */}
        <IconButton
          edge="start"
          onClick={onMenuClick}
          aria-label="Open navigation menu"
          size="small"
          sx={{ mr: 0.5, display: { md: "none" } }}
        >
          <MenuIcon fontSize="small" />
        </IconButton>

        <Typography variant="subtitle1" fontWeight={600} sx={{ flex: 1 }}>
          {title ?? "GATE Platform"}
        </Typography>

        {/* Scan in-progress indicator */}
        {scanProgress && (
          <Box
            aria-live="polite"
            aria-label="Scan in progress"
            sx={{ display: "flex", alignItems: "center", gap: 1 }}
          >
            <CircularProgress size={14} thickness={5} aria-hidden="true" />
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
          aria-hidden="true"
        />
      )}
    </AppBar>
  );
}
