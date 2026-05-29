import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

interface UIState {
  sidebarOpen: boolean;
  selectedSymbol: string | null;
  scanModalOpen: boolean;
  buyModalOpen: boolean;
  buyModalSymbol: string | null;
}

const initialState: UIState = {
  sidebarOpen: true,
  selectedSymbol: null,
  scanModalOpen: false,
  buyModalOpen: false,
  buyModalSymbol: null,
};

export const uiSlice = createSlice({
  name: "ui",
  initialState,
  reducers: {
    toggleSidebar: (state) => {
      state.sidebarOpen = !state.sidebarOpen;
    },
    setSidebarOpen: (state, action: PayloadAction<boolean>) => {
      state.sidebarOpen = action.payload;
    },
    selectSymbol: (state, action: PayloadAction<string | null>) => {
      state.selectedSymbol = action.payload;
    },
    openScanModal: (state) => { state.scanModalOpen = true; },
    closeScanModal: (state) => { state.scanModalOpen = false; },
    openBuyModal: (state, action: PayloadAction<string | null>) => {
      state.buyModalOpen = true;
      state.buyModalSymbol = action.payload;
    },
    closeBuyModal: (state) => {
      state.buyModalOpen = false;
      state.buyModalSymbol = null;
    },
  },
});

export const {
  toggleSidebar,
  setSidebarOpen,
  selectSymbol,
  openScanModal,
  closeScanModal,
  openBuyModal,
  closeBuyModal,
} = uiSlice.actions;
