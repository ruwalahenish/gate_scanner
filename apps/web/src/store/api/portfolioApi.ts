import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type { Position, Trade, PortfolioSummary, BuyRequest, SellRequest } from "@/types/portfolio";
import { API_URL } from "@/lib/constants";

export const portfolioApi = createApi({
  reducerPath: "portfolioApi",
  baseQuery: fetchBaseQuery({ baseUrl: `${API_URL}/api/portfolio` }),
  tagTypes: ["Position", "Trade", "Summary"],
  endpoints: (builder) => ({
    getPortfolioSummary: builder.query<PortfolioSummary, void>({
      query: () => "/summary",
      providesTags: ["Summary"],
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
    buy: builder.mutation<{ position_id: string; trade_id: string; cost: number }, BuyRequest>({
      query: (body) => ({
        url: "/buy",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Position", "Summary"],
    }),
    sell: builder.mutation<{ trade_id: string; pnl_abs: number; pnl_pct: number }, SellRequest>({
      query: (body) => ({
        url: "/sell",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Position", "Trade", "Summary"],
    }),
    updateStopLoss: builder.mutation<{ updated: boolean }, { positionId: string; sl: number; level?: string }>({
      query: ({ positionId, sl, level = "manual" }) => ({
        url: `/positions/${positionId}/sl`,
        method: "PUT",
        params: { sl, level },
      }),
      invalidatesTags: ["Position"],
    }),
    updateCapital: builder.mutation<{ updated: boolean; amount: number }, { amount: number }>({
      query: (body) => ({
        url: "/capital",
        method: "PUT",
        body,
      }),
      invalidatesTags: ["Summary"],
    }),
  }),
});

export const {
  useGetPortfolioSummaryQuery,
  useGetPositionsQuery,
  useGetTradesQuery,
  useBuyMutation,
  useSellMutation,
  useUpdateStopLossMutation,
  useUpdateCapitalMutation,
} = portfolioApi;
