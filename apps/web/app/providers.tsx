"use client";
import { ReactNode } from "react";
import { Provider } from "react-redux";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { SnackbarProvider } from "notistack";
import { store } from "@/store";
import { theme } from "@/lib/theme";
import { useWebSocket } from "@/hooks/useWebSocket";

function WSInitializer() {
  useWebSocket();
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  return (
    <Provider store={store}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <SnackbarProvider
          maxSnack={5}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
          autoHideDuration={5000}
        >
          <WSInitializer />
          {children}
        </SnackbarProvider>
      </ThemeProvider>
    </Provider>
  );
}
