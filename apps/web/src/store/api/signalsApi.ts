import { createApi, fetchBaseQuery, retry } from "@reduxjs/toolkit/query/react";
import type { Signal, SignalListResponse, SignalFilters } from "@/types/signal";
import type { ScanResult } from "@/types/scan";
import { API_URL } from "@/lib/constants";

const baseQueryWithRetry = retry(
  fetchBaseQuery({ baseUrl: `${API_URL}/api` }),
  { maxRetries: 3 }
);

export const signalsApi = createApi({
  reducerPath: "signalsApi",
  baseQuery: baseQueryWithRetry,
  tagTypes: ["Signal", "Scan"],
  endpoints: (builder) => ({
    getSignals: builder.query<SignalListResponse, SignalFilters>({
      query: (filters = {}) => ({
        url: "/signals",
        params: filters,
      }),
      providesTags: ["Signal"],
      keepUnusedDataFor: 300,
    }),
    getSignalHistory: builder.query<Signal[], { symbol: string; limit?: number }>({
      query: ({ symbol, limit = 30 }) => ({
        url: `/signals/${symbol}/history`,
        params: { limit },
      }),
      keepUnusedDataFor: 120,
    }),
    getSymbolAnalysis: builder.query<Record<string, unknown>, string>({
      query: (symbol) => `/signals/${symbol}/analysis`,
      keepUnusedDataFor: 300,
    }),
    getChartData: builder.query<
      { symbol: string; timeframe: string; bars: object[] },
      { symbol: string; timeframe: string }
    >({
      query: ({ symbol, timeframe }) => ({
        url: `/signals/${symbol}/chart-data`,
        params: { timeframe },
      }),
      keepUnusedDataFor: 300,
    }),
    getScans: builder.query<ScanResult[], void>({
      query: () => "/scans",
      providesTags: ["Scan"],
      keepUnusedDataFor: 60,
    }),
    triggerScan: builder.mutation<{ scan_id: string; status: string }, { mode: string; universe?: string[] }>({
      query: (body) => ({
        url: "/scans/trigger",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Signal", "Scan"],
    }),
    getScanStatus: builder.query<{ id: string; status: string; signals_found?: number }, string>({
      query: (scanId) => `/scans/${scanId}`,
      keepUnusedDataFor: 0,
    }),
  }),
});

export const {
  useGetSignalsQuery,
  useGetSignalHistoryQuery,
  useGetSymbolAnalysisQuery,
  useGetChartDataQuery,
  useGetScansQuery,
  useTriggerScanMutation,
  useGetScanStatusQuery,
} = signalsApi;
