import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { API_URL } from "@/lib/constants";
import type { WatchlistItem, WatchlistHistoryEvent } from "@/types/watchlist";

export const watchlistApi = createApi({
  reducerPath: "watchlistApi",
  baseQuery: fetchBaseQuery({ baseUrl: `${API_URL}/api/watchlist` }),
  tagTypes: ["Watchlist", "WatchlistHistory"],
  endpoints: (builder) => ({
    getWatchlist: builder.query<WatchlistItem[], { status?: string; source?: string }>({
      query: ({ status, source } = {}) => ({
        url: "",
        params: { ...(status && { status }), ...(source && { source }) },
      }),
      providesTags: ["Watchlist"],
    }),

    getWatchlistItemHistory: builder.query<WatchlistHistoryEvent[], string>({
      query: (symbol) => `/${symbol}/history`,
      providesTags: (_r, _e, symbol) => [{ type: "WatchlistHistory", id: symbol }],
    }),

    removeFromWatchlist: builder.mutation<{ symbol: string; removed: boolean }, string>({
      query: (symbol) => ({
        url: `/${symbol}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Watchlist"],
    }),
  }),
});

export const {
  useGetWatchlistQuery,
  useGetWatchlistItemHistoryQuery,
  useRemoveFromWatchlistMutation,
} = watchlistApi;
