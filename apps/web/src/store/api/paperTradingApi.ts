import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { API_URL } from "@/lib/constants";
import type { PaperTradingSummary, PaperTradingPerformance, Position, Trade } from "@/types/paper_trading";

export interface SellRequest {
  position_id: string;
  quantity: number;
  price: number;
  exit_reason?: string;
  notes?: string;
}

export const paperTradingApi = createApi({
  reducerPath: "paperTradingApi",
  baseQuery: fetchBaseQuery({ baseUrl: `${API_URL}/api/paper-trading` }),
  tagTypes: ["Position", "Trade", "Summary", "Performance"],
  endpoints: (builder) => ({
    getSummary: builder.query<PaperTradingSummary, void>({
      query: () => "/summary",
      providesTags: ["Summary"],
    }),

    getPerformance: builder.query<PaperTradingPerformance, void>({
      query: () => "/performance",
      providesTags: ["Performance"],
      keepUnusedDataFor: 30,
    }),

    getPositions: builder.query<Position[], void>({
      query: () => "/positions",
      providesTags: ["Position"],
    }),

    getTrades: builder.query<{ total: number; items: Trade[] }, { limit?: number; offset?: number }>({
      query: ({ limit = 50, offset = 0 } = {}) => ({
        url: "/trades",
        params: { limit, offset },
      }),
      providesTags: ["Trade"],
    }),

    // Manual sell override — all buys are auto-created
    sellPosition: builder.mutation<object, SellRequest>({
      query: (body) => ({
        url: "/sell",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Position", "Trade", "Summary", "Performance"],
    }),

    setCapital: builder.mutation<object, { amount: number }>({
      query: (body) => ({
        url: "/capital",
        method: "PUT",
        body,
      }),
      invalidatesTags: ["Summary", "Performance"],
    }),
  }),
});

export const {
  useGetSummaryQuery,
  useGetPerformanceQuery,
  useGetPositionsQuery,
  useGetTradesQuery,
  useSellPositionMutation,
  useSetCapitalMutation,
} = paperTradingApi;
