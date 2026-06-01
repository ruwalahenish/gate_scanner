import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { API_URL } from "@/lib/constants";

export const marketApi = createApi({
  reducerPath: "marketApi",
  baseQuery: fetchBaseQuery({ baseUrl: `${API_URL}/api` }),
  tagTypes: ["Price"],
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
    searchUniverse: builder.query<{ results: string[] }, string>({
      query: (q) => ({ url: "/universe/search", params: { q } }),
    }),
  }),
});

export const {
  useGetPriceQuery,
  useGetBulkPricesQuery,
  useSearchUniverseQuery,
} = marketApi;
