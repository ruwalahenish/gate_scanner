import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { StreamingSignal } from "@/types/scan";

interface ScanProgress {
  done: number;
  total: number;
}

interface PostProcessPayload {
  watch_added: number;
  trades_created: number;
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
  streamingSignals: StreamingSignal[];
  lastPostProcess: PostProcessPayload | null;
  lastCompletionSummary: CompletionSummary | null;
  lastPrices: Record<string, number>;
}

const initialState: WSState = {
  connected: false,
  lastScanId: null,
  currentScanId: null,
  scanProgress: null,
  scanStartedAt: null,
  streamingSignals: [],
  lastPostProcess: null,
  lastCompletionSummary: null,
  lastPrices: {},
};

const BUY_CATS = new Set(["INVESTMENT", "SWING", "POSITIONAL"]);

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
      state.streamingSignals = [];
      state.lastCompletionSummary = null;
    },
    scanProgressReceived: (state, action: PayloadAction<ScanProgress>) => {
      state.scanProgress = action.payload;
    },
    scanBatchReceived: (
      state,
      action: PayloadAction<{ signals: StreamingSignal[]; done: number; total: number }>
    ) => {
      state.streamingSignals.push(...action.payload.signals);
      state.scanProgress = { done: action.payload.done, total: action.payload.total };
    },
    scanCompleted: (
      state,
      action: PayloadAction<{ scan_id: string; signals_count: number }>
    ) => {
      const duration = state.scanStartedAt
        ? (Date.now() - state.scanStartedAt) / 1000
        : 0;
      const sigs = state.streamingSignals;
      state.lastCompletionSummary = {
        scan_id:        action.payload.scan_id,
        signals_count:  action.payload.signals_count,
        buy_count:      sigs.filter(s => BUY_CATS.has(s.category)).length,
        watch_count:    sigs.filter(s => s.category === "WATCH").length,
        no_action_count: sigs.filter(s => s.category === "IGNORE").length,
        duration_sec:   Math.round(duration),
      };
      state.lastScanId    = action.payload.scan_id;
      state.currentScanId = null;
      state.scanProgress  = null;
      state.scanStartedAt = null;
    },
    clearStreamingSignals: (state) => {
      state.streamingSignals = [];
    },
    scanFailed: (state) => {
      state.currentScanId = null;
      state.scanProgress  = null;
      state.scanStartedAt = null;
      state.streamingSignals = [];
    },
    postProcessReceived: (state, action: PayloadAction<PostProcessPayload>) => {
      state.lastPostProcess = action.payload;
    },
    priceUpdated: (state, action: PayloadAction<{ symbol: string; price: number }>) => {
      state.lastPrices[action.payload.symbol] = action.payload.price;
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
  postProcessReceived,
  priceUpdated,
} = wsSlice.actions;
