import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type { Alert, CreateAlertRequest } from "@/types/alert";
import { API_URL } from "@/lib/constants";

export const alertsApi = createApi({
  reducerPath: "alertsApi",
  baseQuery: fetchBaseQuery({ baseUrl: `${API_URL}/api/alerts` }),
  tagTypes: ["Alert"],
  endpoints: (builder) => ({
    getAlerts: builder.query<Alert[], { status?: string } | void>({
      query: (params) => ({ url: "", params: params ?? {} }),
      providesTags: ["Alert"],
    }),
    createAlert: builder.mutation<{ alert_id: string; status: string }, CreateAlertRequest>({
      query: (body) => ({ url: "", method: "POST", body }),
      invalidatesTags: ["Alert"],
    }),
    dismissAlert: builder.mutation<{ dismissed: boolean }, string>({
      query: (alertId) => ({ url: `/${alertId}/dismiss`, method: "POST" }),
      invalidatesTags: ["Alert"],
    }),
    deleteAlert: builder.mutation<{ deleted: boolean }, string>({
      query: (alertId) => ({ url: `/${alertId}`, method: "DELETE" }),
      invalidatesTags: ["Alert"],
    }),
  }),
});

export const {
  useGetAlertsQuery,
  useCreateAlertMutation,
  useDismissAlertMutation,
  useDeleteAlertMutation,
} = alertsApi;
