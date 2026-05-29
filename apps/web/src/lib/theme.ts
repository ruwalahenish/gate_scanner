"use client";
import { createTheme, alpha } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary:   { main: "#6366f1", light: "#818cf8", dark: "#4f46e5" },
    secondary: { main: "#8b5cf6" },
    success:   { main: "#22c55e", light: "#4ade80", dark: "#16a34a" },
    error:     { main: "#ef4444", light: "#f87171", dark: "#dc2626" },
    warning:   { main: "#f59e0b", light: "#fbbf24", dark: "#d97706" },
    info:      { main: "#38bdf8" },
    background: {
      default: "#0f0f12",
      paper:   "#1a1a24",
    },
    text: {
      primary:   "#f1f5f9",
      secondary: "#94a3b8",
      disabled:  "#475569",
    },
    divider: "rgba(255,255,255,0.06)",
  },
  typography: {
    fontFamily: [
      "Inter",
      "-apple-system",
      "BlinkMacSystemFont",
      "Segoe UI",
      "sans-serif",
    ].join(","),
    // Tabular numbers for all price/percentage displays
    body2: { fontVariantNumeric: "tabular-nums" } as any,
    caption: { fontVariantNumeric: "tabular-nums" } as any,
  },
  shape: { borderRadius: 8 },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          scrollbarColor: "#2d2d40 #0f0f12",
          "&::-webkit-scrollbar": { width: 8 },
          "&::-webkit-scrollbar-track": { background: "#0f0f12" },
          "&::-webkit-scrollbar-thumb": {
            background: "#2d2d40",
            borderRadius: 4,
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          border: "1px solid rgba(255,255,255,0.06)",
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { textTransform: "none", fontWeight: 500 },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 500 },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottomColor: "rgba(255,255,255,0.06)",
          fontVariantNumeric: "tabular-nums",
        },
      },
    },
    MuiDataGrid: {
      styleOverrides: {
        root: {
          border: "none",
          "& .MuiDataGrid-columnHeaders": {
            backgroundColor: "#1a1a24",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
          },
          "& .MuiDataGrid-row:hover": {
            backgroundColor: "rgba(99,102,241,0.06)",
          },
          "& .MuiDataGrid-cell": {
            borderBottomColor: "rgba(255,255,255,0.04)",
          },
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: { borderRadius: 4 },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: "#2d2d40",
          border: "1px solid rgba(255,255,255,0.08)",
          fontSize: "0.75rem",
        },
      },
    },
    MuiTextField: {
      defaultProps: { size: "small", variant: "outlined" },
    },
    MuiSelect: {
      defaultProps: { size: "small" },
    },
  },
});
