"use client";
import { useEffect, useRef } from "react";
import { useDispatch } from "react-redux";
import { enqueueSnackbar } from "notistack";
import { WS_URL } from "@/lib/constants";
import {
  setConnected,
  scanProgressReceived,
  scanCompleted,
  alertReceived,
  priceUpdated,
} from "@/store/slices/wsSlice";
import { signalsApi } from "@/store/api/signalsApi";
import { portfolioApi } from "@/store/api/portfolioApi";
import { alertsApi } from "@/store/api/alertsApi";
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
        // Auto-reconnect after 3s
        retryTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string);
          handleMessage(msg, dispatch);
        } catch {
          // ignore malformed messages
        }
      };
    };

    connect();

    // Keepalive ping every 25s
    pingRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send("ping");
      }
    }, 25_000);

    return () => {
      clearTimeout(retryTimeout);
      if (pingRef.current) clearInterval(pingRef.current);
      wsRef.current?.close();
    };
  }, [dispatch]);
}

function handleMessage(msg: { type: string; payload: Record<string, unknown> }, dispatch: AppDispatch) {
  switch (msg.type) {
    case "scan.started":
      enqueueSnackbar("Scan started…", { variant: "info", autoHideDuration: 3000 });
      break;

    case "scan.progress":
      dispatch(scanProgressReceived({
        done: msg.payload.symbols_done as number,
        total: msg.payload.symbols_total as number,
      }));
      break;

    case "scan.complete":
      dispatch(scanCompleted(msg.payload.scan_id as string));
      dispatch(signalsApi.util.invalidateTags(["Signal", "Scan"]));
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

    case "backtest.complete":
      enqueueSnackbar("Backtest complete!", { variant: "success" });
      break;
  }
}
