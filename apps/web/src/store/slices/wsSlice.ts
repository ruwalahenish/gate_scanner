import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { BUY_CATEGORIES } from "@/lib/constants";
import type { StreamingSignal } from "@/types/scan";

const MAX_STREAMING_SIGNALS = 500;

interface ScanProgress {
  done: number;
  total: number;
}

export interface CompletionSummary {
  scan_id: string;
  signals_count: number;
  buy_count: number;
  watch_count: number;
  no_action_count: number;
  duration_sec: number;
}

interface WSState {
  connected: boolean;
  lastScanId: string | null;
  currentScanId: string | null;
  scanProgress: ScanProgress | null;
  scanStartedAt: number | null;
  scanPhase: string | null;
  scanPhaseMessage: string | null;
  streamingSignals: StreamingSignal[];
  // Total signals received (not bounded) — use for display counts in TopBar etc.
  streamingSignalsCount: number;
  streamingBuyCount: number;
  streamingWatchCount: number;
  streamingNoActionCount: number;
  lastCompletionSummary: CompletionSummary | null;
}

const initialState: WSState = {
  connected: false,
  lastScanId: null,
  currentScanId: null,
  scanProgress: null,
  scanStartedAt: null,
  scanPhase: null,
  scanPhaseMessage: null,
  streamingSignals: [],
  streamingSignalsCount: 0,
  streamingBuyCount: 0,
  streamingWatchCount: 0,
  streamingNoActionCount: 0,
  lastCompletionSummary: null,
};

function resetStreamingCounters(state: WSState) {
  state.streamingSignals = [];
  state.streamingSignalsCount = 0;
  state.streamingBuyCount = 0;
  state.streamingWatchCount = 0;
  state.streamingNoActionCount = 0;
}

export const wsSlice = createSlice({
  name: "ws",
  initialState,
  reducers: {
    setConnected: (state, action: PayloadAction<boolean>) => {
      state.connected = action.payload;
    },
    scanStarted: (state, action: PayloadAction<string | undefined>) => {
      state.scanProgress    = { done: 0, total: 0 };
      state.currentScanId   = action.payload ?? null;
      state.scanStartedAt   = Date.now();
      state.scanPhase       = null;
      state.scanPhaseMessage = null;
      state.lastCompletionSummary = null;
      resetStreamingCounters(state);
    },
    scanPhaseReceived: (state, action: PayloadAction<{ phase: string; message: string }>) => {
      state.scanPhase       = action.payload.phase;
      state.scanPhaseMessage = action.payload.message;
    },
    scanProgressReceived: (state, action: PayloadAction<ScanProgress & { scan_id?: string }>) => {
      // Ignore stale progress from a scan that isn't the one we're tracking —
      // e.g. an orphaned worker still churning through a scan the user already
      // stopped, whose late events would otherwise flip isScanning back to true.
      if (state.currentScanId && action.payload.scan_id && action.payload.scan_id !== state.currentScanId) {
        return;
      }
      state.scanProgress = { done: action.payload.done, total: action.payload.total };
    },
    scanBatchReceived: (
      state,
      action: PayloadAction<{ scan_id?: string; signals: StreamingSignal[]; done: number; total: number }>
    ) => {
      if (state.currentScanId && action.payload.scan_id && action.payload.scan_id !== state.currentScanId) {
        return;
      }
      const incoming = action.payload.signals;
      // Bound the display array to the last MAX_STREAMING_SIGNALS items.
      const combined = [...state.streamingSignals, ...incoming];
      state.streamingSignals = combined.length > MAX_STREAMING_SIGNALS
        ? combined.slice(-MAX_STREAMING_SIGNALS)
        : combined;

      // Maintain exact running counts for TopBar indicators (not bounded by slice).
      state.streamingSignalsCount += incoming.length;
      for (const sig of incoming) {
        if (BUY_CATEGORIES.has(sig.category))  state.streamingBuyCount++;
        else if (sig.category === "WATCH")     state.streamingWatchCount++;
        else                                   state.streamingNoActionCount++;
      }

      state.scanProgress = { done: action.payload.done, total: action.payload.total };
    },
    scanCompleted: (
      state,
      action: PayloadAction<{ scan_id: string; signals_count: number }>
    ) => {
      // A scan the user already stopped (currentScanId cleared) shouldn't be
      // able to post a late completion summary for itself.
      if (state.currentScanId && action.payload.scan_id !== state.currentScanId) {
        return;
      }
      const duration = state.scanStartedAt
        ? (Date.now() - state.scanStartedAt) / 1000
        : 0;
      // Use running counters — accurate even when array is bounded.
      state.lastCompletionSummary = {
        scan_id:         action.payload.scan_id,
        signals_count:   action.payload.signals_count,
        buy_count:       state.streamingBuyCount,
        watch_count:     state.streamingWatchCount,
        no_action_count: state.streamingNoActionCount,
        duration_sec:    Math.round(duration),
      };
      state.lastScanId      = action.payload.scan_id;
      state.currentScanId   = null;
      state.scanProgress    = null;
      state.scanStartedAt   = null;
      state.scanPhase       = null;
      state.scanPhaseMessage = null;
    },
    clearStreamingSignals: (state) => {
      resetStreamingCounters(state);
    },
    scanFailed: (state) => {
      state.currentScanId    = null;
      state.scanProgress     = null;
      state.scanStartedAt    = null;
      state.scanPhase        = null;
      state.scanPhaseMessage = null;
      resetStreamingCounters(state);
    },
  },
});

export const {
  setConnected,
  scanStarted,
  scanProgressReceived,
  scanBatchReceived,
  scanCompleted,
  clearStreamingSignals,
  scanFailed,
  scanPhaseReceived,
} = wsSlice.actions;
