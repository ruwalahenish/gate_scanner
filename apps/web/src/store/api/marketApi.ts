import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { API_URL } from "@/lib/constants";

export const marketApi = createApi({
  reducerPath: "marketApi",
  baseQuery: fetchBaseQuery({ baseUrl: `${API_URL}/api` }),
  tagTypes: ["Price", "Watchlist"],
  endpoints: (builder) => ({
    getPrice: builder.query<{ symbol: string; price: number }, string>({
      query: (symbol) => `/market/price/${symbol}`,
      keepUnusedDataFor: 60,
    }),
    getBulkPrices: builder.query<{ prices: Record<string, number> }, string[]>({
      query: (symbols) => ({
        url: "/market/prices",
        params: { symbols: symbols.join(",") },
      }),
      keepUnusedDataFor: 60,
    }),
    getWatchlist: builder.query<object[], void>({
      query: () => "/watchlist",
      providesTags: ["Watchlist"],
    }),
    addToWatchlist: builder.mutation<{ symbol: string; added: boolean }, string>({
      query: (symbol) => ({
        url: "/watchlist",
        method: "POST",
        params: { symbol },
      }),
      invalidatesTags: ["Watchlist"],
    }),
    removeFromWatchlist: builder.mutation<{ symbol: string; removed: boolean }, string>({
      query: (symbol) => ({
        url: `/watchlist/${symbol}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Watchlist"],
    }),
    searchUniverse: builder.query<{ results: string[] }, string>({
      query: (q) => ({ url: "/universe/search", params: { q } }),
    }),
  }),
});

export const {
  useGetPriceQuery,
  useGetBulkPricesQuery,
  useGetWatchlistQuery,
  useAddToWatchlistMutation,
  useRemoveFromWatchlistMutation,
  useSearchUniverseQuery,
} = marketApi;
