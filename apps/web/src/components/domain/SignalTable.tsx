"use client";
import { useState, useCallback, memo } from "react";
import {
  Box, Chip, Typography, IconButton, Collapse,
  useTheme, useMediaQuery,
} from "@mui/material";
import { ExpandMore, ExpandLess } from "@mui/icons-material";
import { GATEBar } from "@/components/ui/GATEBar";
import { StockLink } from "@/components/ui/StockLink";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { TradeSetupPanel } from "@/components/domain/TradeSetupPanel";
import { WatchSetupLoader } from "@/components/domain/WatchSetupLoader";
import { fromSignal } from "@/lib/tradeSetup";
import { formatPrice, formatRR } from "@/lib/formatters";
import { STATUS_COLORS, CATEGORY_DISPLAY } from "@/lib/constants";
import type { Signal, SignalCategory } from "@/types/signal";

// Re-exported for backwards compatibility (canonical source: lib/constants.ts)
export { CATEGORY_DISPLAY };

// ─────────────────────────────────────────────────────────────────────────────
// Constants — defined outside components to prevent sx object recreation
// ─────────────────────────────────────────────────────────────────────────────

const GRID_DESKTOP = "32px minmax(100px,140px) minmax(120px,160px) 90px 85px 72px 48px 56px";
const HEADERS      = ["", "Symbol", "Status", "GATE", "Entry", "SL", "RR", "TF"] as const;

const HEADER_SX = {
  display: "grid",
  gridTemplateColumns: GRID_DESKTOP,
  gap: 1,
  px: 1,
  py: 0.6,
  borderBottom: "1px solid rgba(255,255,255,0.08)",
  bgcolor: "rgba(0,0,0,0.15)",
} as const;

const ROW_SX = {
  display: "grid",
  gridTemplateColumns: GRID_DESKTOP,
  alignItems: "center",
  gap: 1,
  px: 1,
  py: 0.75,
  cursor: "pointer",
  "&:hover": { bgcolor: "rgba(255,255,255,0.025)" },
  "&:focus-visible": { outline: "2px solid rgba(99,102,241,0.5)", outlineOffset: -2 },
} as const;

const ROW_EXPANDED_SX = {
  ...ROW_SX,
  borderBottom: "none",
} as const;

const ROW_COLLAPSED_SX = {
  ...ROW_SX,
  borderBottom: "1px solid rgba(255,255,255,0.04)",
} as const;

const SIGNAL_DETAIL_SX = {
  px: { xs: 1, sm: 1.5 },
  py: 1.5,
  borderTop: "1px solid rgba(255,255,255,0.06)",
} as const;

const TF_CHIP_SX = {
  fontSize: "0.62rem",
  height: 18,
  bgcolor: "rgba(99,102,241,0.12)",
  color: "#818cf8",
  border: "1px solid rgba(99,102,241,0.25)",
} as const;

const MOBILE_ROW_SX = {
  p: 1.5,
  borderBottom: "1px solid rgba(255,255,255,0.04)",
  cursor: "pointer",
  "&:hover": { bgcolor: "rgba(255,255,255,0.025)" },
  "&:focus-visible": { outline: "2px solid rgba(99,102,241,0.5)", outlineOffset: -2 },
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components (all memoized — pure functions of props)
// ─────────────────────────────────────────────────────────────────────────────

const StatusChip = memo(function StatusChip({ category, displayCategory }: {
  category: SignalCategory;
  displayCategory?: string | null;
}) {
  const label = displayCategory ?? CATEGORY_DISPLAY[category]?.label ?? category;
  const color = STATUS_COLORS[label as keyof typeof STATUS_COLORS] ?? "#64748b";
  return (
    <Chip
      label={label}
      size="small"
      sx={{
        bgcolor: `${color}1a`,
        color,
        border: `1px solid ${color}40`,
        fontWeight: 600,
        fontSize: "0.65rem",
        height: 20,
        maxWidth: 145,
      }}
    />
  );
});

// Expanded row detail — routes to the shared TradeSetupPanel. BUY/levelled
// signals render their stored setup instantly; WATCH signals (no stored levels)
// get an on-demand "Load trade setup" loader that runs the live GATE engine.
const SignalDetail = memo(function SignalDetail({ signal }: { signal: Signal }) {
  const hasLevels = signal.entry != null;
  return (
    <Box sx={SIGNAL_DETAIL_SX}>
      {hasLevels ? (
        <TradeSetupPanel setup={fromSignal(signal)} variant="full" headerTitle="Trade Setup" />
      ) : (
        <WatchSetupLoader
          symbol={signal.symbol}
          category={signal.category}
          initialSetup={fromSignal(signal, "anticipated")}
          variant="full"
          headerTitle="Trade Setup"
        />
      )}
    </Box>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Signal rows
// ─────────────────────────────────────────────────────────────────────────────

const DesktopSignalRow = memo(function DesktopSignalRow({ signal, expanded, onToggle }: {
  signal: Signal;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <Box
        tabIndex={0}
        role="row"
        aria-expanded={expanded}
        onClick={onToggle}
        onKeyDown={(e) => e.key === "Enter" && onToggle()}
        sx={expanded ? ROW_EXPANDED_SX : ROW_COLLAPSED_SX}
      >
        <IconButton
          size="small"
          onClick={(e) => { e.stopPropagation(); onToggle(); }}
          aria-label={expanded ? "Collapse signal detail" : "Expand signal detail"}
          sx={{ p: 0.3 }}
        >
          {expanded ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
        </IconButton>

        <Box>
          <StockLink symbol={signal.symbol} variant="body2" fontWeight={700} color="primary.light" lineHeight={1.2} />
          {signal.company_name && (
            <Typography variant="caption" color="text.disabled" noWrap sx={{ display: "block", fontSize: "0.62rem" }}>
              {signal.company_name}
            </Typography>
          )}
        </Box>

        <StatusChip category={signal.category} displayCategory={signal.display_category} />
        <GATEBar score={signal.gate_strength} />

        <Typography variant="body2" sx={{ fontSize: "0.78rem" }}>
          {formatPrice(signal.entry)}
        </Typography>
        <Typography variant="body2" color="error.light" sx={{ fontSize: "0.78rem" }}>
          {formatPrice(signal.stop_loss)}
        </Typography>
        <Typography
          variant="body2"
          fontWeight={600}
          sx={{ fontSize: "0.78rem", color: (signal.rr_t1 ?? 0) >= 2 ? "success.main" : "text.primary" }}
        >
          {formatRR(signal.rr_t1)}
        </Typography>
        <Chip label="Daily" size="small" sx={TF_CHIP_SX} />
      </Box>
      <Collapse in={expanded} unmountOnExit>
        <SignalDetail signal={signal} />
      </Collapse>
    </>
  );
});

const MobileSignalRow = memo(function MobileSignalRow({ signal, expanded, onToggle }: {
  signal: Signal;
  expanded: boolean;
  onToggle: () => void;
}) {
  const rrColor = (signal.rr_t1 ?? 0) >= 2 ? "success.main" : "text.primary";
  return (
    <>
      <Box
        tabIndex={0}
        role="row"
        aria-expanded={expanded}
        onClick={onToggle}
        onKeyDown={(e) => e.key === "Enter" && onToggle()}
        sx={MOBILE_ROW_SX}
      >
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={0.75}>
          <Box>
            <StockLink symbol={signal.symbol} variant="body2" fontWeight={700} color="primary.light" lineHeight={1.2} />
            {signal.company_name && (
              <Typography variant="caption" color="text.disabled" sx={{ fontSize: "0.62rem" }}>
                {signal.company_name}
              </Typography>
            )}
          </Box>
          <StatusChip category={signal.category} displayCategory={signal.display_category} />
        </Box>
        <Box display="flex" gap={1.5} alignItems="center" flexWrap="wrap">
          <Box sx={{ minWidth: 80, flex: 1 }}>
            <GATEBar score={signal.gate_strength} />
          </Box>
          <Typography variant="caption" color="text.secondary">
            {formatPrice(signal.entry)}
          </Typography>
          <Typography variant="caption" color="error.light">
            SL: {formatPrice(signal.stop_loss)}
          </Typography>
          <Typography variant="caption" fontWeight={600} sx={{ color: rrColor }}>
            {formatRR(signal.rr_t1)}
          </Typography>
        </Box>
      </Box>
      <Collapse in={expanded} unmountOnExit>
        <SignalDetail signal={signal} />
      </Collapse>
    </>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Column headers (desktop only)
// ─────────────────────────────────────────────────────────────────────────────

const TableHeaders = memo(function TableHeaders() {
  return (
    <Box role="row" sx={HEADER_SX}>
      {HEADERS.map((h) => (
        <Typography key={h} role="columnheader" variant="caption" color="text.disabled" sx={{ fontSize: "0.7rem", fontWeight: 600 }}>
          {h}
        </Typography>
      ))}
    </Box>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Public export
// ─────────────────────────────────────────────────────────────────────────────

interface SignalTableProps {
  signals: Signal[];
  loading?: boolean;
}

export function SignalTable({ signals, loading }: SignalTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const theme    = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"), { noSsr: true });

  const toggle = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  if (loading) {
    return (
      <Box role="table" aria-label="Scan results loading">
        {!isMobile && <TableHeaders />}
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} variant="signal-row" />
        ))}
      </Box>
    );
  }

  return (
    <Box role="table" aria-label="Scan results">
      {!isMobile && <TableHeaders />}
      {signals.map((sig) =>
        isMobile ? (
          <MobileSignalRow
            key={sig.id}
            signal={sig}
            expanded={expandedId === sig.id}
            onToggle={() => toggle(sig.id)}
          />
        ) : (
          <DesktopSignalRow
            key={sig.id}
            signal={sig}
            expanded={expandedId === sig.id}
            onToggle={() => toggle(sig.id)}
          />
        )
      )}
    </Box>
  );
}
