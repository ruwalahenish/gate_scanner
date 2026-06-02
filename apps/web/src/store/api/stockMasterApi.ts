import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { API_URL } from "@/lib/constants";
import type {
  BacktestTrade,
  Bar,
  Stock,
  StockFilters,
  StockListResponse,
  StockSearchResult,
  StockSyncStats,
  SyncTaskStatus,
} from "@/types/stock";

export const stockMasterApi = createApi({
  reducerPath: "stockMasterApi",
  baseQuery: fetchBaseQuery({ baseUrl: `${API_URL}/api/stocks` }),
  tagTypes: ["Stock", "StockSync"],
  endpoints: (builder) => ({
    searchStocks: builder.query<StockSearchResult[], string>({
      query: (q) => ({ url: "/search", params: { q } }),
      keepUnusedDataFor: 300,
    }),
    getStock: builder.query<Stock, string>({
      query: (symbol) => `/${symbol}`,
      providesTags: (_, __, symbol) => [{ type: "Stock", id: symbol }],
    }),
    listStocks: builder.query<StockListResponse, StockFilters>({
      query: (filters = {}) => ({ url: "", params: filters }),
      providesTags: ["Stock"],
    }),
    getStockStats: builder.query<StockSyncStats, void>({
      query: () => "/stats",
      providesTags: ["StockSync"],
    }),
    triggerSync: builder.mutation<{ task_id: string; status: string }, { phases: string[] }>({
      query: (body) => ({ url: "/sync/trigger", method: "POST", body }),
      invalidatesTags: ["StockSync"],
    }),
    getSyncStatus: builder.query<SyncTaskStatus, void>({
      query: () => "/sync/status",
    }),
    // Chart data with EMA overlays
    getStockChartData: builder.query<{ symbol: string; timeframe: string; bars: Bar[] }, { symbol: string; timeframe: string }>({
      query: ({ symbol, timeframe }) => ({
        url: `/${symbol}/chart-data`,
        params: { timeframe },
      }),
      keepUnusedDataFor: 300,
    }),
    // Live GATE analysis (~5s, expensive — cached 5 min)
    getStockAnalysis: builder.query<Record<string, unknown>, string>({
      query: (symbol) => `/${symbol}/analysis`,
      keepUnusedDataFor: 300,
    }),
    // Per-symbol backtest trade history
    getStockBacktestTrades: builder.query<BacktestTrade[], { symbol: string; limit?: number }>({
      query: ({ symbol, limit = 50 }) => ({
        url: `/${symbol}/backtest-trades`,
        params: { limit },
      }),
    }),
  }),
});

export const {
  useSearchStocksQuery,
  useGetStockQuery,
  useListStocksQuery,
  useGetStockStatsQuery,
  useTriggerSyncMutation,
  useGetSyncStatusQuery,
  useGetStockChartDataQuery,
  useGetStockAnalysisQuery,
  useGetStockBacktestTradesQuery,
} = stockMasterApi;
