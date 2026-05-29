import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

interface ScanProgress {
  done: number;
  total: number;
}

interface WSState {
  connected: boolean;
  lastScanId: string | null;
  scanProgress: ScanProgress | null;
  unreadAlerts: number;
  lastPrices: Record<string, number>;
}

const initialState: WSState = {
  connected: false,
  lastScanId: null,
  scanProgress: null,
  unreadAlerts: 0,
  lastPrices: {},
};

export const wsSlice = createSlice({
  name: "ws",
  initialState,
  reducers: {
    setConnected: (state, action: PayloadAction<boolean>) => {
      state.connected = action.payload;
    },
    scanProgressReceived: (state, action: PayloadAction<ScanProgress>) => {
      state.scanProgress = action.payload;
    },
    scanCompleted: (state, action: PayloadAction<string>) => {
      state.lastScanId = action.payload;
      state.scanProgress = null;
    },
    alertReceived: (state) => {
      state.unreadAlerts += 1;
    },
    alertsRead: (state) => {
      state.unreadAlerts = 0;
    },
    priceUpdated: (state, action: PayloadAction<{ symbol: string; price: number }>) => {
      state.lastPrices[action.payload.symbol] = action.payload.price;
    },
  },
});

export const {
  setConnected,
  scanProgressReceived,
  scanCompleted,
  alertReceived,
  alertsRead,
  priceUpdated,
} = wsSlice.actions;
