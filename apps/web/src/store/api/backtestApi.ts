import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { API_URL } from "@/lib/constants";
import type { BacktestStatusResponse } from "@/types/stock";
import type { LiveStockResult } from "@/store/slices/wsSlice";

export const backtestApi = createApi({
  reducerPath: "backtestApi",
  baseQuery: fetchBaseQuery({ baseUrl: `${API_URL}/api/backtests` }),
  tagTypes: ["Backtest"],
  endpoints: (builder) => ({
    getBacktestStatus: builder.query<BacktestStatusResponse, string>({
      query: (id) => `/${id}`,
      providesTags: (_, __, id) => [{ type: "Backtest", id }],
    }),
    cancelBacktest: builder.mutation<{ status: string }, string>({
      query: (id) => ({ url: `/${id}/cancel`, method: "POST" }),
    }),
    getStockResults: builder.query<LiveStockResult[], string>({
      query: (id) => `/${id}/stock-results`,
      providesTags: (_, __, id) => [{ type: "Backtest", id }],
    }),
  }),
});

export const {
  useGetBacktestStatusQuery,
  useCancelBacktestMutation,
  useGetStockResultsQuery,
} = backtestApi;
