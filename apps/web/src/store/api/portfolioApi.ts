import { createApi, fetchBaseQuery, retry } from "@reduxjs/toolkit/query/react";
import type { Position, Trade, PortfolioSummary, BuyRequest, SellRequest } from "@/types/portfolio";
import { API_URL } from "@/lib/constants";

// Retry up to 3 times on network errors, with exponential back-off
const baseQueryWithRetry = retry(
  fetchBaseQuery({ baseUrl: `${API_URL}/api/portfolio` }),
  { maxRetries: 3 }
);

export const portfolioApi = createApi({
  reducerPath: "portfolioApi",
  baseQuery: baseQueryWithRetry,
  tagTypes: ["Position", "Trade", "Summary"],
  endpoints: (builder) => ({
    getPortfolioSummary: builder.query<PortfolioSummary, void>({
      query: () => "/summary",
      providesTags: ["Summary"],
      keepUnusedDataFor: 60,
    }),
    getPositions: builder.query<Position[], void>({
      query: () => "/positions",
      providesTags: ["Position"],
      keepUnusedDataFor: 30,
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
      // Optimistic update: add a placeholder position immediately
      onQueryStarted: async (arg, { dispatch, queryFulfilled }) => {
        const patch = dispatch(
          portfolioApi.util.updateQueryData("getPositions", undefined, (draft) => {
            draft.push({
              id: `optimistic-${Date.now()}`,
              symbol: arg.symbol,
              side: "BUY",
              quantity: arg.quantity,
              avg_entry: arg.price,
              stop_loss: arg.stop_loss ?? null,
              t1: arg.t1 ?? null,
              t2: arg.t2 ?? null,
              t3: arg.t3 ?? null,
              trailing_sl: null,
              signal_id: arg.signal_id ?? null,
              opened_at: new Date().toISOString(),
              status: "open",
              notes: arg.notes ?? null,
            } as Position)
          })
        );
        try {
          await queryFulfilled;
        } catch {
          patch.undo();
        }
      },
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
