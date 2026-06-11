"use client";
import { useState, useCallback, memo } from "react";
import {
  Box, Chip, Typography, IconButton, Collapse,
  Paper, Grid, Divider, LinearProgress,
  useTheme, useMediaQuery,
} from "@mui/material";
import { ExpandMore, ExpandLess, CheckCircle, Cancel } from "@mui/icons-material";
import { GATEBar } from "@/components/ui/GATEBar";
import { StockLink } from "@/components/ui/StockLink";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { formatPrice, formatRR } from "@/lib/formatters";
import { STATUS_COLORS, GATE_THRESHOLDS, GATE_COLOR } from "@/lib/constants";
import type { Signal, SignalCategory, DisplayStatus } from "@/types/signal";

// ─────────────────────────────────────────────────────────────────────────────
// Constants — defined outside components to prevent sx object recreation
// ─────────────────────────────────────────────────────────────────────────────

export const CATEGORY_DISPLAY: Record<SignalCategory, { label: string; display: DisplayStatus }> = {
  INVESTMENT: { label: "Long-Term Buy",  display: "BUY"       },
  SWING:      { label: "Swing Buy",      display: "BUY"       },
  POSITIONAL: { label: "Positional Buy", display: "BUY"       },
  WATCH:      { label: "Watch",          display: "WATCH"     },
  IGNORE:     { label: "No Action",      display: "NO_ACTION" },
};

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

const EXPANDED_PAPER_SX = {
  p: 2,
  bgcolor: "rgba(99,102,241,0.04)",
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

const ScoreBar = memo(function ScoreBar({ label, value }: { label: string; value: number | null | undefined }) {
  const v     = value ?? 0;
  const pct   = Math.min(100, Math.max(0, v));
  const color =
    pct >= GATE_THRESHOLDS.HIGH ? GATE_COLOR.HIGH :
    pct >= GATE_THRESHOLDS.MID  ? GATE_COLOR.MID  :
    pct >= GATE_THRESHOLDS.LOW  ? GATE_COLOR.LOW  : GATE_COLOR.FAIL;
  return (
    <Box mb={0.6}>
      <Box display="flex" justifyContent="space-between" mb={0.2}>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.68rem" }}>{label}</Typography>
        <Typography variant="caption" fontWeight={600} sx={{ fontSize: "0.68rem", color }}>
          {value != null ? value.toFixed(0) : "—"}
        </Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{
          height: 3,
          borderRadius: 2,
          bgcolor: "rgba(255,255,255,0.06)",
          "& .MuiLinearProgress-bar": { bgcolor: color, borderRadius: 2 },
        }}
      />
    </Box>
  );
});

const BoolFlag = memo(function BoolFlag({ val, label }: { val: boolean | null | undefined; label: string }) {
  const ok = val === true;
  return (
    <Box display="flex" alignItems="center" gap={0.6} mb={0.4}>
      {ok
        ? <CheckCircle sx={{ fontSize: 13, color: "success.main" }} aria-hidden="true" />
        : <Cancel     sx={{ fontSize: 13, color: val === false ? "error.main" : "text.disabled" }} aria-hidden="true" />}
      <Typography variant="caption" color={ok ? "text.primary" : "text.disabled"} sx={{ fontSize: "0.7rem" }}>
        {label}
      </Typography>
    </Box>
  );
});

const ExpandedDetail = memo(function ExpandedDetail({ signal }: { signal: Signal }) {
  return (
    <Paper elevation={0} sx={EXPANDED_PAPER_SX}>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={4}>
          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.8}>
            SIGNAL LEVELS
          </Typography>
          {[
            ["Entry",     signal.entry,     "primary.light"],
            ["Stop Loss", signal.stop_loss, "error.light"  ],
            ["T1",        signal.t1,        "success.light"],
            ["T2",        signal.t2,        "success.main" ],
            ["T3",        signal.t3,        "success.dark" ],
          ].map(([label, val, color]) => (
            <Box key={String(label)} display="flex" justifyContent="space-between" mb={0.4}>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.7rem" }}>{label}</Typography>
              <Typography variant="caption" fontWeight={600} sx={{ color: color as string, fontSize: "0.7rem" }}>
                {val != null ? formatPrice(val as number) : "—"}
              </Typography>
            </Box>
          ))}
          <Box mt={0.8}>
            <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.6}>
              QUALITY FLAGS
            </Typography>
            <BoolFlag val={signal.htf_confirmed}         label="HTF Confirmed"        />
            <BoolFlag val={signal.correction_validated}  label="Correction Validated" />
            <BoolFlag val={signal.bounce_sequence_valid} label="Bounce Sequence"      />
            <BoolFlag val={signal.fib_confluence}        label="Fib Confluence"       />
          </Box>
        </Grid>

        <Grid item xs={12} sm={4}>
          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.8}>
            SCORES
          </Typography>
          <ScoreBar label="GATE Score"        value={signal.gate_strength}          />
          <ScoreBar label="Confidence"        value={signal.confidence}             />
          <ScoreBar label="Structure Quality" value={signal.structure_quality}      />
          <ScoreBar label="MTF Alignment"     value={signal.mtf_alignment_pct}      />
          <ScoreBar label="Breakout Prob"     value={signal.breakout_probability}   />
          <ScoreBar label="Vol Compression"   value={signal.volatility_compression} />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.8}>
            DETAILS
          </Typography>
          {[
            ["Timeframe",    signal.signal_timeframe ],
            ["SL Timeframe", signal.sl_timeframe     ],
            ["Trend",        signal.trend_direction  ],
            ["Phase",        signal.phase            ],
            ["SL Distance",  signal.sl_distance_pct != null ? `${signal.sl_distance_pct.toFixed(1)}%` : null],
            ["ATR",          signal.atr != null ? signal.atr.toFixed(2) : null],
          ].map(([label, val]) => (
            <Box key={String(label)} display="flex" justifyContent="space-between" mb={0.4}>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.7rem" }}>{label}</Typography>
              <Typography variant="caption" fontWeight={500} sx={{ fontSize: "0.7rem" }}>{val ?? "—"}</Typography>
            </Box>
          ))}
        </Grid>

        {signal.reasoning && (
          <Grid item xs={12}>
            <Divider sx={{ borderColor: "rgba(255,255,255,0.06)", mb: 1 }} />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.72rem", lineHeight: 1.6 }}>
              {signal.reasoning}
            </Typography>
          </Grid>
        )}
      </Grid>
    </Paper>
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
          {signal.entry != null ? `₹${signal.entry.toLocaleString("en-IN")}` : "—"}
        </Typography>
        <Typography variant="body2" color="error.light" sx={{ fontSize: "0.78rem" }}>
          {signal.stop_loss != null ? `₹${signal.stop_loss.toLocaleString("en-IN")}` : "—"}
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
        <ExpandedDetail signal={signal} />
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
            {signal.entry != null ? `₹${signal.entry.toLocaleString("en-IN")}` : "—"}
          </Typography>
          <Typography variant="caption" color="error.light">
            SL: {signal.stop_loss != null ? `₹${signal.stop_loss.toLocaleString("en-IN")}` : "—"}
          </Typography>
          <Typography variant="caption" fontWeight={600} sx={{ color: rrColor }}>
            {formatRR(signal.rr_t1)}
          </Typography>
        </Box>
      </Box>
      <Collapse in={expanded} unmountOnExit>
        <ExpandedDetail signal={signal} />
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
