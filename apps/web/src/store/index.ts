import { configureStore } from "@reduxjs/toolkit";
import { scannerApi } from "./api/scannerApi";
import { marketApi } from "./api/marketApi";
import { stockMasterApi } from "./api/stockMasterApi";
// Legacy — still used by stock detail pages; will be removed in M7
import { signalsApi } from "./api/signalsApi";
import { wsSlice } from "./slices/wsSlice";
import { uiSlice } from "./slices/uiSlice";

export const store = configureStore({
  reducer: {
    ui:                               uiSlice.reducer,
    ws:                               wsSlice.reducer,
    [scannerApi.reducerPath]:         scannerApi.reducer,
    [marketApi.reducerPath]:          marketApi.reducer,
    [stockMasterApi.reducerPath]:     stockMasterApi.reducer,
    [signalsApi.reducerPath]:         signalsApi.reducer,
  },
  middleware: (getDefault) =>
    getDefault().concat(
      scannerApi.middleware,
      marketApi.middleware,
      stockMasterApi.middleware,
      signalsApi.middleware,
    ),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
