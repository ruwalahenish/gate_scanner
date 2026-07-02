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
  scanPhaseReceived,
} from "@/store/slices/wsSlice";
import { scannerApi } from "@/store/api/scannerApi";
import { stockMasterApi } from "@/store/api/stockMasterApi";
import type { AppDispatch } from "@/store";

// Reconnect backoff: 3s → 6s → 12s → 24s → capped at 30s.
const RETRY_BASE_MS = 3_000;
const RETRY_MAX_MS  = 30_000;

export function useWebSocket() {
  const dispatch = useDispatch<AppDispatch>();
  const wsRef    = useRef<WebSocket | null>(null);
  const pingRef  = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let retryTimeout: ReturnType<typeof setTimeout>;
    let retryAttempts = 0;
    let disposed = false;

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
          handleMessage(msg, dispatch);
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

    return () => {
      disposed = true;
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
      enqueueSnackbar(
        `Scan complete — ${msg.payload.signals_count} signals found`,
        { variant: "success", autoHideDuration: 5000 }
      );
      break;

    case "scan.phase":
      dispatch(scanPhaseReceived({
        phase:   msg.payload.phase   as string,
        message: msg.payload.message as string,
      }));
      break;

    case "scan.failed":
      dispatch(scanFailed());
      enqueueSnackbar(
        `Scan failed: ${(msg.payload.error as string) ?? "unknown error"}`,
        { variant: "error", autoHideDuration: 6000 }
      );
      break;
  }
}
