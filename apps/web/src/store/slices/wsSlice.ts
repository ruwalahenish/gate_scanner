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

export interface LiveStockResult {
  symbol: string;
  status: "done" | "failed";
  total_trades: number;
  winning_trades: number;
  win_rate: number;
  total_pnl_abs: number;
  avg_pnl_pct: number;
  best_trade_pct: number;
  worst_trade_pct: number;
  avg_holding_days: number;
  category: string | null;
  error?: string;
  completed: number;
  total: number;
}

interface BacktestLiveProgress {
  completed: number;
  total: number;
  currentBatch: string[];
}

interface BacktestLiveState {
  backtest_id: string | null;
  stockResults: LiveStockResult[];
  progress: BacktestLiveProgress | null;
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
  backtestLive: BacktestLiveState;
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
  backtestLive: {
    backtest_id: null,
    stockResults: [],
    progress: null,
  },
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
    // ── Backtest live-streaming actions ──────────────────────────────────────
    backtestLiveReset: (state, action: PayloadAction<string>) => {
      state.backtestLive = {
        backtest_id: action.payload,
        stockResults: [],
        progress: null,
      };
    },
    backtestLiveLoad: (state, action: PayloadAction<{ backtest_id: string; results: LiveStockResult[] }>) => {
      state.backtestLive = {
        backtest_id: action.payload.backtest_id,
        stockResults: action.payload.results,
        progress: null,
      };
    },
    backtestBatchScanning: (
      state,
      action: PayloadAction<{ symbols: string[]; completed: number; total: number }>
    ) => {
      state.backtestLive.progress = {
        completed:    action.payload.completed,
        total:        action.payload.total,
        currentBatch: action.payload.symbols,
      };
    },
    backtestStockComplete: (state, action: PayloadAction<LiveStockResult>) => {
      const idx = state.backtestLive.stockResults.findIndex(
        r => r.symbol === action.payload.symbol
      );
      if (idx >= 0) {
        state.backtestLive.stockResults[idx] = action.payload;
      } else {
        state.backtestLive.stockResults.push(action.payload);
      }
      state.backtestLive.progress = {
        completed:    action.payload.completed,
        total:        action.payload.total,
        currentBatch: state.backtestLive.progress?.currentBatch ?? [],
      };
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
  backtestLiveReset,
  backtestLiveLoad,
  backtestBatchScanning,
  backtestStockComplete,
} = wsSlice.actions;
