import { configureStore } from "@reduxjs/toolkit";
import { signalsApi } from "./api/signalsApi";
import { portfolioApi } from "./api/portfolioApi";
import { alertsApi } from "./api/alertsApi";
import { marketApi } from "./api/marketApi";
import { stockMasterApi } from "./api/stockMasterApi";
import { wsSlice } from "./slices/wsSlice";
import { uiSlice } from "./slices/uiSlice";

export const store = configureStore({
  reducer: {
    ui:                             uiSlice.reducer,
    ws:                             wsSlice.reducer,
    [signalsApi.reducerPath]:       signalsApi.reducer,
    [portfolioApi.reducerPath]:     portfolioApi.reducer,
    [alertsApi.reducerPath]:        alertsApi.reducer,
    [marketApi.reducerPath]:        marketApi.reducer,
    [stockMasterApi.reducerPath]:   stockMasterApi.reducer,
  },
  middleware: (getDefault) =>
    getDefault().concat(
      signalsApi.middleware,
      portfolioApi.middleware,
      alertsApi.middleware,
      marketApi.middleware,
      stockMasterApi.middleware,
    ),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
