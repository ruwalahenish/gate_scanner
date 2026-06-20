import { createSelector } from "@reduxjs/toolkit";
import type { RootState } from "./index";

// ── Raw state selectors ──────────────────────────────────────────────────────

export const selectScanProgress        = (s: RootState) => s.ws.scanProgress;
export const selectScanPhaseMessage    = (s: RootState) => s.ws.scanPhaseMessage;
export const selectCurrentScanId       = (s: RootState) => s.ws.currentScanId;
export const selectWsConnected         = (s: RootState) => s.ws.connected;
export const selectCompletionSummary   = (s: RootState) => s.ws.lastCompletionSummary;
export const selectLastPostProcess     = (s: RootState) => s.ws.lastPostProcess;
export const selectScanStartedAt       = (s: RootState) => s.ws.scanStartedAt;
export const selectBacktestLive        = (s: RootState) => s.ws.backtestLive;
export const selectStreamingSignals    = (s: RootState) => s.ws.streamingSignals;
export const selectStreamingCount      = (s: RootState) => s.ws.streamingSignalsCount;
export const selectStreamingBuyCount   = (s: RootState) => s.ws.streamingBuyCount;
export const selectStreamingWatchCount = (s: RootState) => s.ws.streamingWatchCount;
export const selectStreamingNoActCount = (s: RootState) => s.ws.streamingNoActionCount;
export const selectLastScanId          = (s: RootState) => s.ws.lastScanId;
export const selectLastPrices          = (s: RootState) => s.ws.lastPrices;

export const selectSidebarOpen    = (s: RootState) => s.ui.sidebarOpen;
export const selectBuyModalOpen   = (s: RootState) => s.ui.buyModalOpen;
export const selectBuyModalSymbol = (s: RootState) => s.ui.buyModalSymbol;
export const selectSelectedSymbol = (s: RootState) => s.ui.selectedSymbol;

// ── Computed (memoized) selectors ────────────────────────────────────────────

export const selectIsScanning = createSelector(
  selectScanProgress,
  (progress) => progress !== null
);

export const selectHasRealProgress = createSelector(
  selectScanProgress,
  (progress) => progress !== null && progress.total > 0
);

export const selectScanProgressPct = createSelector(
  selectScanProgress,
  (progress) => {
    if (!progress || progress.total === 0) return 0;
    return Math.min(100, Math.round((progress.done / progress.total) * 100));
  }
);
