"use client";
import { createTheme } from "@mui/material/styles";

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
    h6: {
      fontWeight: 700,
      fontSize: "1rem",
      lineHeight: 1.4,
    },
    subtitle1: {
      fontWeight: 600,
      fontSize: "0.875rem",
    },
    subtitle2: {
      fontWeight: 700,
      fontSize: "0.8125rem",
    },
    body2:   { fontVariantNumeric: "tabular-nums", fontSize: "0.8125rem" },
    caption: { fontVariantNumeric: "tabular-nums" },
    overline: {
      fontSize: "0.65rem",
      fontWeight: 600,
      letterSpacing: "0.08em",
      lineHeight: 1.6,
    },
  },

  shape: { borderRadius: 8 },

  // Custom shadow scale for dark-theme depth (indices 1,2,4,8 overridden).
  shadows: [
    "none",
    "0 1px 4px rgba(0,0,0,0.4)",
    "0 2px 12px rgba(0,0,0,0.5)",
    "0 2px 16px rgba(0,0,0,0.5)",
    "0 4px 24px rgba(0,0,0,0.6)",
    "0 4px 24px rgba(0,0,0,0.65)",
    "0 6px 32px rgba(0,0,0,0.65)",
    "0 6px 32px rgba(0,0,0,0.7)",
    "0 8px 40px rgba(0,0,0,0.7)",
    "0 8px 40px rgba(0,0,0,0.75)",
    "0 10px 48px rgba(0,0,0,0.75)",
    "0 10px 48px rgba(0,0,0,0.8)",
    "0 12px 56px rgba(0,0,0,0.8)",
    "0 12px 56px rgba(0,0,0,0.82)",
    "0 14px 60px rgba(0,0,0,0.82)",
    "0 14px 60px rgba(0,0,0,0.85)",
    "0 16px 64px rgba(0,0,0,0.85)",
    "0 16px 64px rgba(0,0,0,0.87)",
    "0 18px 68px rgba(0,0,0,0.87)",
    "0 18px 68px rgba(0,0,0,0.9)",
    "0 20px 72px rgba(0,0,0,0.9)",
    "0 20px 72px rgba(0,0,0,0.92)",
    "0 22px 76px rgba(0,0,0,0.92)",
    "0 24px 80px rgba(0,0,0,0.94)",
    "0 24px 80px rgba(0,0,0,0.95)",
  ],

  transitions: {
    duration: {
      shortest:   150,
      shorter:    200,
      short:      250,
      standard:   300,
      complex:    375,
      enteringScreen: 225,
      leavingScreen:  195,
    },
  },

  components: {
    // ── Global baseline ─────────────────────────────────────────────────
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          scrollbarColor: "#2d2d40 #0f0f12",
          "&::-webkit-scrollbar":       { width: 6 },
          "&::-webkit-scrollbar-track": { background: "#0f0f12" },
          "&::-webkit-scrollbar-thumb": {
            background: "#2d2d40",
            borderRadius: 3,
            "&:hover": { background: "#3d3d58" },
          },
        },
        // Focus-visible: show outline only on keyboard navigation, not mouse clicks.
        "*, *::before, *::after": {
          "&:focus-visible": {
            outline: "2px solid rgba(99,102,241,0.7)",
            outlineOffset: 2,
          },
          "&:focus:not(:focus-visible)": {
            outline: "none",
          },
        },
        // Suppress double-ring on MUI Tabs which manage their own focus indicator.
        ".MuiTab-root:focus-visible": {
          outline: "none",
        },
      },
    },

    // ── Surface ─────────────────────────────────────────────────────────
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          border: "1px solid rgba(255,255,255,0.07)",
          transition: "border-color 200ms ease, box-shadow 200ms ease",
          "&:hover": {
            borderColor: "rgba(255,255,255,0.1)",
            boxShadow: "0 2px 12px rgba(0,0,0,0.5)",
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
      },
    },

    // ── Inputs ──────────────────────────────────────────────────────────
    MuiTextField: {
      defaultProps: { size: "small", variant: "outlined" },
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            "&:hover .MuiOutlinedInput-notchedOutline": {
              borderColor: "rgba(99,102,241,0.5)",
            },
            "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
              borderColor: "#6366f1",
              borderWidth: 1.5,
            },
          },
        },
      },
    },
    MuiSelect: {
      defaultProps: { size: "small" },
      styleOverrides: {
        icon: { color: "#64748b" },
      },
    },

    // ── Buttons ─────────────────────────────────────────────────────────
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 500,
          transition: "box-shadow 200ms ease, background-color 200ms ease",
          "&.MuiButton-containedPrimary": {
            boxShadow: "0 1px 6px rgba(99,102,241,0.3)",
            "&:hover": { boxShadow: "0 2px 12px rgba(99,102,241,0.45)" },
          },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          borderRadius: "8px",
          transition: "background-color 150ms ease",
          "&:hover": { bgcolor: "rgba(255,255,255,0.06)" },
          "&:focus-visible": {
            outline: "2px solid rgba(99,102,241,0.6)",
            outlineOffset: 2,
          },
        },
      },
    },

    // ── Chip ────────────────────────────────────────────────────────────
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
          transition: "background-color 150ms ease, border-color 150ms ease",
        },
      },
    },

    // ── Tabs ────────────────────────────────────────────────────────────
    MuiTabs: {
      styleOverrides: {
        root: { minHeight: 40 },
        indicator: {
          height: 2,
          borderRadius: "2px 2px 0 0",
          backgroundColor: "#6366f1",
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 500,
          minHeight: 40,
          color: "#64748b",
          transition: "color 150ms ease",
          "&.Mui-selected": { color: "#818cf8", fontWeight: 600 },
          "&:hover":        { color: "#94a3b8" },
        },
      },
    },

    // ── Dialog ──────────────────────────────────────────────────────────
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundImage: "none",
          backgroundColor: "#1e1e2e",
          border: "1px solid rgba(255,255,255,0.1)",
          boxShadow: "0 25px 60px rgba(0,0,0,0.7)",
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: {
        root: {
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          pb: 1.5,
          fontWeight: 700,
          fontSize: "1rem",
        },
      },
    },

    // ── Alert ───────────────────────────────────────────────────────────
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 8, fontSize: "0.82rem" },
        standardInfo:    { backgroundColor: "rgba(56,189,248,0.08)",  border: "1px solid rgba(56,189,248,0.2)"  },
        standardSuccess: { backgroundColor: "rgba(34,197,94,0.08)",   border: "1px solid rgba(34,197,94,0.2)"   },
        standardWarning: { backgroundColor: "rgba(245,158,11,0.08)",  border: "1px solid rgba(245,158,11,0.2)"  },
        standardError:   { backgroundColor: "rgba(239,68,68,0.08)",   border: "1px solid rgba(239,68,68,0.2)"   },
      },
    },

    // ── Table ───────────────────────────────────────────────────────────
    MuiTableHead: {
      styleOverrides: {
        root: {
          "& .MuiTableCell-head": {
            backgroundColor: "rgba(0,0,0,0.25)",
            fontWeight: 600,
            fontSize: "0.72rem",
            color: "#64748b",
            letterSpacing: "0.03em",
            textTransform: "uppercase",
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottomColor: "rgba(255,255,255,0.05)",
          fontVariantNumeric: "tabular-nums",
          padding: "6px 12px",
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          "&:hover": { backgroundColor: "rgba(99,102,241,0.04)" },
          "&:last-child .MuiTableCell-body": { borderBottom: "none" },
        },
      },
    },

    // ── Pagination ──────────────────────────────────────────────────────
    MuiPaginationItem: {
      styleOverrides: {
        root: {
          color: "#64748b",
          border: "1px solid rgba(255,255,255,0.08)",
          "&.Mui-selected": {
            backgroundColor: "rgba(99,102,241,0.2)",
            color: "#818cf8",
            borderColor: "rgba(99,102,241,0.35)",
          },
          "&:hover": {
            backgroundColor: "rgba(255,255,255,0.05)",
          },
        },
      },
    },

    // ── Progress ────────────────────────────────────────────────────────
    MuiLinearProgress: {
      styleOverrides: {
        root: { borderRadius: 4 },
      },
    },

    // ── Tooltip ─────────────────────────────────────────────────────────
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: "#2d2d40",
          border: "1px solid rgba(255,255,255,0.1)",
          fontSize: "0.73rem",
          lineHeight: 1.5,
          maxWidth: 260,
        },
        arrow: { color: "#2d2d40" },
      },
    },

    // ── ListItemButton ───────────────────────────────────────────────────
    MuiListItemButton: {
      styleOverrides: {
        root: {
          transition: "background-color 150ms ease",
          "&.Mui-selected": {
            "&:hover": { backgroundColor: "rgba(99,102,241,0.2)" },
          },
        },
      },
    },

    // ── Drawer ──────────────────────────────────────────────────────────
    MuiDrawer: {
      styleOverrides: {
        paper: {
          "@media (max-width: 899px)": {
            boxShadow: "4px 0 24px rgba(0,0,0,0.6)",
          },
        },
      },
    },

    // ── Stepper ─────────────────────────────────────────────────────────
    MuiStepLabel: {
      styleOverrides: {
        label: { color: "#94a3b8", "&.Mui-active": { color: "#f1f5f9" } },
      },
    },
    MuiStepIcon: {
      styleOverrides: {
        root: {
          color: "rgba(255,255,255,0.1)",
          "&.Mui-active": { color: "#6366f1" },
        },
        text: { fill: "#fff" },
      },
    },

    // ── Divider ─────────────────────────────────────────────────────────
    MuiDivider: {
      styleOverrides: {
        root: { borderColor: "rgba(255,255,255,0.06)" },
      },
    },

    // ── AppBar ──────────────────────────────────────────────────────────
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          backgroundColor: "#15151f",
          borderBottom: "1px solid rgba(255,255,255,0.07)",
        },
      },
    },

    // ── DataGrid (requires @mui/x-data-grid module augmentation) ────────
    // @ts-expect-error — MuiDataGrid component overrides require @mui/x-data-grid module augmentation
    MuiDataGrid: {
      styleOverrides: {
        root: {
          border: "none",
          "& .MuiDataGrid-columnHeaders": {
            backgroundColor: "rgba(0,0,0,0.2)",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
          },
          "& .MuiDataGrid-columnHeaderTitle": {
            fontSize: "0.72rem",
            fontWeight: 600,
            color: "#64748b",
            textTransform: "uppercase",
            letterSpacing: "0.03em",
          },
          "& .MuiDataGrid-row:hover": {
            backgroundColor: "rgba(99,102,241,0.05)",
          },
          "& .MuiDataGrid-cell": {
            borderBottomColor: "rgba(255,255,255,0.04)",
          },
          "& .MuiDataGrid-footerContainer": {
            borderTopColor: "rgba(255,255,255,0.06)",
          },
        },
      },
    },
  },
});
