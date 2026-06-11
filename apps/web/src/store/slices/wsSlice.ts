import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { BUY_CATEGORIES } from "@/lib/constants";
import type { StreamingSignal } from "@/types/scan";

const MAX_STREAMING_SIGNALS = 500;

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
  // Total signals received (not bounded) — use for display counts in TopBar etc.
  streamingSignalsCount: number;
  streamingBuyCount: number;
  streamingWatchCount: number;
  streamingNoActionCount: number;
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
  streamingSignalsCount: 0,
  streamingBuyCount: 0,
  streamingWatchCount: 0,
  streamingNoActionCount: 0,
  lastPostProcess: null,
  lastCompletionSummary: null,
  lastPrices: {},
  backtestLive: {
    backtest_id: null,
    stockResults: [],
    progress: null,
  },
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
      state.lastCompletionSummary = null;
      resetStreamingCounters(state);
    },
    scanProgressReceived: (state, action: PayloadAction<ScanProgress>) => {
      state.scanProgress = action.payload;
    },
    scanBatchReceived: (
      state,
      action: PayloadAction<{ signals: StreamingSignal[]; done: number; total: number }>
    ) => {
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
      state.lastScanId    = action.payload.scan_id;
      state.currentScanId = null;
      state.scanProgress  = null;
      state.scanStartedAt = null;
    },
    clearStreamingSignals: (state) => {
      resetStreamingCounters(state);
    },
    scanFailed: (state) => {
      state.currentScanId = null;
      state.scanProgress  = null;
      state.scanStartedAt = null;
      resetStreamingCounters(state);
    },
    postProcessReceived: (state, action: PayloadAction<PostProcessPayload>) => {
      state.lastPostProcess = action.payload;
    },
    priceUpdated: (state, action: PayloadAction<{ symbol: string; price: number }>) => {
      state.lastPrices[action.payload.symbol] = action.payload.price;
    },
    // Batched variant — useWebSocket buffers price ticks and flushes them
    // periodically so the store (and every subscribed component) updates at
    // most once per flush instead of once per tick.
    pricesBatchUpdated: (state, action: PayloadAction<Record<string, number>>) => {
      Object.assign(state.lastPrices, action.payload);
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
  pricesBatchUpdated,
  backtestLiveReset,
  backtestLiveLoad,
  backtestBatchScanning,
  backtestStockComplete,
} = wsSlice.actions;
