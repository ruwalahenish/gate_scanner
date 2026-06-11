"use client";
import { useEffect, useRef } from "react";
import { useDispatch } from "react-redux";
import { enqueueSnackbar } from "notistack";
import { WS_URL } from "@/lib/constants";
import {
  setConnected,
  scanStarted,
  scanProgressReceived,
  scanBatchReceived,
  scanCompleted,
  clearStreamingSignals,
  scanFailed,
  postProcessReceived,
  pricesBatchUpdated,
  backtestBatchScanning,
  backtestStockComplete,
  type LiveStockResult,
} from "@/store/slices/wsSlice";
import { scannerApi } from "@/store/api/scannerApi";
import { paperTradingApi } from "@/store/api/paperTradingApi";
import { watchlistApi } from "@/store/api/watchlistApi";
import { stockMasterApi } from "@/store/api/stockMasterApi";
import { backtestApi } from "@/store/api/backtestApi";
import type { AppDispatch } from "@/store";

// Reconnect backoff: 3s → 6s → 12s → 24s → capped at 30s.
const RETRY_BASE_MS = 3_000;
const RETRY_MAX_MS  = 30_000;

// Price ticks are buffered and flushed at this interval so the Redux store
// (and every subscribed component) updates at most once per flush — not once
// per tick. Each flush also triggers at most ONE positions refetch.
const PRICE_FLUSH_MS = 1_500;

export function useWebSocket() {
  const dispatch = useDispatch<AppDispatch>();
  const wsRef    = useRef<WebSocket | null>(null);
  const pingRef  = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let retryTimeout: ReturnType<typeof setTimeout>;
    let retryAttempts = 0;
    let disposed = false;

    const priceBuffer = new Map<string, number>();

    const connect = () => {
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        retryAttempts = 0;
        dispatch(setConnected(true));
      };
      ws.onclose = () => {
        dispatch(setConnected(false));
        if (disposed) return;
        const delay = Math.min(RETRY_BASE_MS * 2 ** retryAttempts, RETRY_MAX_MS);
        retryAttempts += 1;
        retryTimeout = setTimeout(connect, delay);
      };
      ws.onerror = () => ws.close();

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string);
          handleMessage(msg, dispatch, priceBuffer);
        } catch (e) {
          console.warn("[ws] malformed message", e);
        }
      };
    };

    connect();

    pingRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 25_000);

    const priceFlush = setInterval(() => {
      if (priceBuffer.size === 0) return;
      dispatch(pricesBatchUpdated(Object.fromEntries(priceBuffer)));
      priceBuffer.clear();
      dispatch(paperTradingApi.util.invalidateTags(["Position", "Summary"]));
    }, PRICE_FLUSH_MS);

    return () => {
      disposed = true;
      clearTimeout(retryTimeout);
      if (pingRef.current) clearInterval(pingRef.current);
      clearInterval(priceFlush);
      wsRef.current?.close();
    };
  }, [dispatch]);
}

function handleMessage(
  msg: { type: string; payload: Record<string, unknown> },
  dispatch: AppDispatch,
  priceBuffer: Map<string, number>
) {
  switch (msg.type) {
    case "scan.started":
      dispatch(scanStarted(msg.payload.scan_id as string | undefined));
      enqueueSnackbar("Scan started…", { variant: "info", autoHideDuration: 3000 });
      break;

    case "scan.progress":
      dispatch(scanProgressReceived({
        done:  msg.payload.symbols_done  as number,
        total: msg.payload.symbols_total as number,
      }));
      break;

    case "scan.batch":
      dispatch(scanBatchReceived({
        signals: (msg.payload.signals as []) ?? [],
        done:    msg.payload.done  as number,
        total:   msg.payload.total as number,
      }));
      break;

    case "scan.complete":
      dispatch(scanCompleted({
        scan_id:       msg.payload.scan_id       as string,
        signals_count: msg.payload.signals_count as number ?? 0,
      }));
      dispatch(scannerApi.util.invalidateTags(["Signal", "Scan", "Dashboard"]));
      dispatch(stockMasterApi.util.invalidateTags(["Stock", "Analysis"]));
      setTimeout(() => dispatch(clearStreamingSignals()), 5000);
      // Single completion notification — the post_process event below updates
      // data silently (its summary is shown on the dashboard banner).
      enqueueSnackbar(
        `Scan complete — ${msg.payload.signals_count} signals found`,
        { variant: "success", autoHideDuration: 5000 }
      );
      break;

    case "scan.post_process": {
      const watch  = msg.payload.watch_added    as number;
      const trades = msg.payload.trades_created as number;
      dispatch(postProcessReceived({ watch_added: watch, trades_created: trades }));
      dispatch(watchlistApi.util.invalidateTags(["Watchlist"]));
      dispatch(paperTradingApi.util.invalidateTags(["Position", "Trade", "Summary", "Performance"]));
      break;
    }

    case "price.update":
      // Buffered — flushed periodically by the interval in useWebSocket.
      priceBuffer.set(msg.payload.symbol as string, msg.payload.price as number);
      break;

    case "trade.monitor": {
      const closed = msg.payload.positions_closed as number;
      dispatch(paperTradingApi.util.invalidateTags(["Position", "Trade", "Summary", "Performance"]));
      if (closed > 0) {
        enqueueSnackbar(
          `Auto-exit: ${closed} position${closed !== 1 ? "s" : ""} closed automatically`,
          { variant: "info", autoHideDuration: 5000 }
        );
      }
      break;
    }

    case "scan.failed":
      dispatch(scanFailed());
      enqueueSnackbar(
        `Scan failed: ${(msg.payload.error as string) ?? "unknown error"}`,
        { variant: "error", autoHideDuration: 6000 }
      );
      break;

    // ── Backtest streaming events ────────────────────────────────────────────

    case "backtest.batch_scanning":
      dispatch(backtestBatchScanning({
        symbols:   msg.payload.symbols   as string[],
        completed: msg.payload.completed as number,
        total:     msg.payload.total     as number,
      }));
      break;

    case "backtest.stock_complete":
      dispatch(backtestStockComplete(msg.payload as unknown as LiveStockResult));
      break;

    case "backtest.complete":
      // No snackbar here — the backtest page's own status handler notifies the
      // user who is actually watching the run.
      dispatch(backtestApi.util.invalidateTags(["Backtest"]));
      break;
  }
}
