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
  alertReceived,
  priceUpdated,
} from "@/store/slices/wsSlice";
import { signalsApi } from "@/store/api/signalsApi";
import { portfolioApi } from "@/store/api/portfolioApi";
import { alertsApi } from "@/store/api/alertsApi";
import { stockMasterApi } from "@/store/api/stockMasterApi";
import type { AppDispatch } from "@/store";

export function useWebSocket() {
  const dispatch = useDispatch<AppDispatch>();
  const wsRef = useRef<WebSocket | null>(null);
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let retryTimeout: ReturnType<typeof setTimeout>;

    const connect = () => {
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        dispatch(setConnected(true));
      };

      ws.onclose = () => {
        dispatch(setConnected(false));
        retryTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string);
          handleMessage(msg, dispatch);
        } catch (e) {
          console.warn("[ws] malformed message", e);
        }
      };
    };

    connect();

    // Keepalive ping every 25s
    pingRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 25_000);

    return () => {
      clearTimeout(retryTimeout);
      if (pingRef.current) clearInterval(pingRef.current);
      wsRef.current?.close();
    };
  }, [dispatch]);
}

function handleMessage(
  msg: { type: string; payload: Record<string, unknown> },
  dispatch: AppDispatch
) {
  switch (msg.type) {
    case "scan.started":
      dispatch(scanStarted(msg.payload.scan_id as string | undefined));
      enqueueSnackbar("Scan started…", { variant: "info", autoHideDuration: 3000 });
      break;

    case "scan.progress":
      dispatch(scanProgressReceived({
        done: msg.payload.symbols_done as number,
        total: msg.payload.symbols_total as number,
      }));
      break;

    case "scan.batch":
      dispatch(scanBatchReceived({
        signals: (msg.payload.signals as []) ?? [],
        done: msg.payload.done as number,
        total: msg.payload.total as number,
      }));
      break;

    case "scan.complete":
      dispatch(scanCompleted(msg.payload.scan_id as string));
      // Invalidate signal/scan cache (dashboard + signal queries)
      dispatch(signalsApi.util.invalidateTags(["Signal", "Scan"]));
      // Invalidate stock cache — this makes the /stocks page auto-refresh its
      // GATE columns (latest_category, latest_gate_strength, entry, SL, etc.)
      dispatch(stockMasterApi.util.invalidateTags(["Stock"]));
      // Clear streaming signals after a short delay (allow RTK Query to repopulate first)
      setTimeout(() => dispatch(clearStreamingSignals()), 2000);
      enqueueSnackbar(
        `Scan complete — ${msg.payload.signals_count} signals found`,
        { variant: "success", autoHideDuration: 5000 }
      );
      break;

    case "alert.triggered":
      dispatch(alertReceived());
      dispatch(alertsApi.util.invalidateTags(["Alert"]));
      enqueueSnackbar(msg.payload.message as string, {
        variant: "warning",
        autoHideDuration: 8000,
      });
      break;

    case "price.update":
      dispatch(priceUpdated({
        symbol: msg.payload.symbol as string,
        price: msg.payload.price as number,
      }));
      dispatch(portfolioApi.util.invalidateTags(["Position", "Summary"]));
      break;

    case "scan.failed":
      dispatch(scanFailed());
      enqueueSnackbar(
        `Scan failed: ${(msg.payload.error as string) ?? "unknown error"}`,
        { variant: "error", autoHideDuration: 6000 }
      );
      break;

    case "backtest.complete":
      enqueueSnackbar("Backtest complete!", { variant: "success" });
      break;
  }
}
