import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { API_URL } from "@/lib/constants";
import type { SignalListResponse } from "@/types/signal";
import type { ScanResult } from "@/types/scan";

export interface ScanFilters {
  status?: "BUY" | "WATCH" | "NO_ACTION";
  min_rank?: number;
  min_gate?: number;
  side?: string;
  // timeframe is always "1d" — not exposed as a filter in the daily strategy platform
  limit?: number;
  offset?: number;
}

export interface SignalCounts {
  total: number;
  buy_count: number;
  watch_count: number;
  no_action_count: number;
}

export interface TriggerScanRequest {
  mode?: string;
  universe?: string[];
}

export interface ScanSchedule {
  id: number;
  enabled: boolean;
  cron_expression: string;
  mode: string;
  last_triggered_at: string | null;
  next_scheduled_at: string | null;
  updated_at: string;
}

export interface DashboardData {
  scanner: {
    last_scan_at: string | null;
    last_scan_duration_sec: number | null;
    total_signals: number;
    buy_count: number;
    watch_count: number;
    no_action_count: number;
  };
  paper_trading: {
    open_positions: number;
    total_trades: number;
    winning_trades: number;
    win_rate: number;
    realized_pnl: number;
    unrealized_pnl: number;
    total_pnl: number;
    current_capital: number;
  };
  backtesting: {
    total_runs: number;
    last_run_at: string | null;
    best_cagr: number;
    best_win_rate: number;
  };
  recent_opportunities: SignalListResponse["items"];
  recent_trades: object[];
  system_health: {
    db_ok: boolean;
    redis_ok: boolean;
    last_scan_duration_sec: number | null;
  };
}

export const scannerApi = createApi({
  reducerPath: "scannerApi",
  baseQuery: fetchBaseQuery({ baseUrl: `${API_URL}/api` }),
  tagTypes: ["Signal", "Scan", "Dashboard", "Schedule"],
  endpoints: (builder) => ({
    // ── Dashboard ──────────────────────────────────────────────────────────
    getDashboard: builder.query<DashboardData, void>({
      query: () => "/v1/dashboard",
      providesTags: ["Dashboard"],
      keepUnusedDataFor: 60,
    }),

    // ── Scan results ───────────────────────────────────────────────────────
    getScanResults: builder.query<SignalListResponse, ScanFilters>({
      query: (filters) => ({
        url: "/scans/latest/signals",
        params: filters,
      }),
      providesTags: ["Signal"],
    }),

    getSignalCounts: builder.query<SignalCounts, void>({
      query: () => "/scans/latest/signals/counts",
      providesTags: ["Signal"],
      keepUnusedDataFor: 120,
    }),

    // ── Scan management ────────────────────────────────────────────────────
    triggerScan: builder.mutation<{ scan_id: string }, TriggerScanRequest>({
      query: (body) => ({
        url: "/scans/trigger",
        method: "POST",
        body: { mode: "daily", universe: [], ...body },
      }),
      invalidatesTags: ["Scan"],
    }),

    stopScan: builder.mutation<{ stopped: boolean; scan_id: string }, string>({
      query: (scan_id) => ({
        url: `/scans/${scan_id}/stop`,
        method: "POST",
      }),
      invalidatesTags: ["Scan", "Dashboard"],
    }),

    getScanStatus: builder.query<ScanResult, string>({
      query: (scanId) => `/scans/${scanId}`,
      providesTags: (_r, _e, id) => [{ type: "Scan", id }],
    }),

    listScans: builder.query<ScanResult[], void>({
      query: () => "/scans",
      providesTags: ["Scan"],
    }),

    // ── Schedule ───────────────────────────────────────────────────────────
    getScanSchedule: builder.query<ScanSchedule, void>({
      query: () => "/scans/schedule",
      providesTags: ["Schedule"],
    }),

    updateScanSchedule: builder.mutation<
      ScanSchedule,
      Partial<Pick<ScanSchedule, "enabled" | "cron_expression" | "mode">>
    >({
      query: (body) => ({
        url: "/scans/schedule",
        method: "PUT",
        body,
      }),
      invalidatesTags: ["Schedule"],
    }),
  }),
});

export const {
  useGetDashboardQuery,
  useGetScanResultsQuery,
  useGetSignalCountsQuery,
  useTriggerScanMutation,
  useStopScanMutation,
  useGetScanStatusQuery,
  useListScansQuery,
  useGetScanScheduleQuery,
  useUpdateScanScheduleMutation,
} = scannerApi;
