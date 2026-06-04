import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { API_URL } from "@/lib/constants";
import type { BacktestStatusResponse } from "@/types/stock";

export const backtestApi = createApi({
  reducerPath: "backtestApi",
  baseQuery: fetchBaseQuery({ baseUrl: `${API_URL}/api/backtests` }),
  endpoints: (builder) => ({
    getBacktestStatus: builder.query<BacktestStatusResponse, string>({
      query: (id) => `/${id}`,
    }),
    cancelBacktest: builder.mutation<{ status: string }, string>({
      query: (id) => ({ url: `/${id}/cancel`, method: "POST" }),
    }),
  }),
});

export const {
  useGetBacktestStatusQuery,
  useCancelBacktestMutation,
} = backtestApi;
