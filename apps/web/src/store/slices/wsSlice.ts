import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { StreamingSignal } from "@/types/scan";

interface ScanProgress {
  done: number;
  total: number;
}

interface WSState {
  connected: boolean;
  lastScanId: string | null;
  currentScanId: string | null;
  scanProgress: ScanProgress | null;
  streamingSignals: StreamingSignal[];
  unreadAlerts: number;
  lastPrices: Record<string, number>;
}

const initialState: WSState = {
  connected: false,
  lastScanId: null,
  currentScanId: null,
  scanProgress: null,
  streamingSignals: [],
  unreadAlerts: 0,
  lastPrices: {},
};

export const wsSlice = createSlice({
  name: "ws",
  initialState,
  reducers: {
    setConnected: (state, action: PayloadAction<boolean>) => {
      state.connected = action.payload;
    },
    scanStarted: (state, action: PayloadAction<string | undefined>) => {
      state.scanProgress = { done: 0, total: 0 };
      state.currentScanId = action.payload ?? null;
      state.streamingSignals = [];
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
    scanCompleted: (state, action: PayloadAction<string>) => {
      state.lastScanId = action.payload;
      state.currentScanId = null;
      state.scanProgress = null;
      // streamingSignals cleared after RTK Query refresh (see useWebSocket handler)
    },
    clearStreamingSignals: (state) => {
      state.streamingSignals = [];
    },
    scanFailed: (state) => {
      state.currentScanId = null;
      state.scanProgress = null;
      state.streamingSignals = [];
    },
    alertReceived: (state) => {
      state.unreadAlerts += 1;
    },
    alertsRead: (state) => {
      state.unreadAlerts = 0;
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
  alertReceived,
  alertsRead,
  priceUpdated,
} = wsSlice.actions;
