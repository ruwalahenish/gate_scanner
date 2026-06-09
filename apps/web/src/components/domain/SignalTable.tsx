"use client";
import { useState } from "react";
import {
  Box, Chip, Typography, IconButton, Collapse,
  Paper, Grid, Divider, LinearProgress,
} from "@mui/material";
import { ExpandMore, ExpandLess, CheckCircle, Cancel } from "@mui/icons-material";
import { GATEBar } from "@/components/ui/GATEBar";
import { formatPrice, formatRR } from "@/lib/formatters";
import type { Signal, SignalCategory, DisplayStatus } from "@/types/signal";

// ─────────────────────────────────────────────────────────────────────────────
// Display-status colour + label maps
// ─────────────────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  "Long-Term Buy":  "#22c55e",
  "Swing Buy":      "#6366f1",
  "Positional Buy": "#38bdf8",
  "Watch":          "#f59e0b",
  "No Action":      "#64748b",
};

// Derive display_category from internal category when not pre-populated by API
export const CATEGORY_DISPLAY: Record<SignalCategory, { label: string; display: DisplayStatus }> = {
  INVESTMENT: { label: "Long-Term Buy",  display: "BUY"       },
  SWING:      { label: "Swing Buy",      display: "BUY"       },
  POSITIONAL: { label: "Positional Buy", display: "BUY"       },
  WATCH:      { label: "Watch",          display: "WATCH"     },
  IGNORE:     { label: "No Action",      display: "NO_ACTION" },
};

function StatusChip({ category, displayCategory }: {
  category: SignalCategory;
  displayCategory?: string | null;
}) {
  const label = displayCategory ?? CATEGORY_DISPLAY[category]?.label ?? category;
  const color = STATUS_COLOR[label] ?? "#64748b";
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
        maxWidth: 130,
      }}
    />
  );
}

function ScoreBar({ label, value }: { label: string; value: number | null | undefined }) {
  const v = value ?? 0;
  const pct = Math.min(100, Math.max(0, v));
  const color = pct >= 70 ? "#22c55e" : pct >= 50 ? "#6366f1" : pct >= 35 ? "#f59e0b" : "#ef4444";
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
}

function BoolFlag({ val, label }: { val: boolean | null | undefined; label: string }) {
  const ok = val === true;
  return (
    <Box display="flex" alignItems="center" gap={0.6} mb={0.4}>
      {ok
        ? <CheckCircle sx={{ fontSize: 13, color: "success.main" }} />
        : <Cancel sx={{ fontSize: 13, color: val === false ? "error.main" : "text.disabled" }} />}
      <Typography variant="caption" color={ok ? "text.primary" : "text.disabled"} sx={{ fontSize: "0.7rem" }}>
        {label}
      </Typography>
    </Box>
  );
}

function ExpandedDetail({ signal }: { signal: Signal }) {
  return (
    <Paper
      elevation={0}
      sx={{ p: 2, bgcolor: "rgba(99,102,241,0.04)", borderTop: "1px solid rgba(255,255,255,0.06)" }}
    >
      <Grid container spacing={2}>
        {/* Signal levels */}
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
            <BoolFlag val={signal.htf_confirmed}        label="HTF Confirmed"       />
            <BoolFlag val={signal.correction_validated} label="Correction Validated" />
            <BoolFlag val={signal.bounce_sequence_valid} label="Bounce Sequence"     />
            <BoolFlag val={signal.fib_confluence}       label="Fib Confluence"       />
          </Box>
        </Grid>

        {/* Score bars */}
        <Grid item xs={12} sm={4}>
          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.8}>
            SCORES
          </Typography>
          <ScoreBar label="GATE Score"          value={signal.gate_strength}        />
          <ScoreBar label="Confidence"          value={signal.confidence}           />
          <ScoreBar label="Structure Quality"   value={signal.structure_quality}    />
          <ScoreBar label="MTF Alignment"       value={signal.mtf_alignment_pct}    />
          <ScoreBar label="Breakout Prob"       value={signal.breakout_probability} />
          <ScoreBar label="Vol Compression"     value={signal.volatility_compression} />
        </Grid>

        {/* Metadata */}
        <Grid item xs={12} sm={4}>
          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.8}>
            DETAILS
          </Typography>
          {[
            ["Timeframe",      signal.signal_timeframe ],
            ["SL Timeframe",   signal.sl_timeframe     ],
            ["Trend",          signal.trend_direction  ],
            ["Phase",          signal.phase            ],
            ["SL Distance",    signal.sl_distance_pct != null ? `${signal.sl_distance_pct.toFixed(1)}%` : null],
            ["ATR",            signal.atr != null ? signal.atr.toFixed(2) : null],
          ].map(([label, val]) => (
            <Box key={String(label)} display="flex" justifyContent="space-between" mb={0.4}>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.7rem" }}>{label}</Typography>
              <Typography variant="caption" fontWeight={500} sx={{ fontSize: "0.7rem" }}>
                {val ?? "—"}
              </Typography>
            </Box>
          ))}
        </Grid>

        {/* Reasoning */}
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
}

// ─────────────────────────────────────────────────────────────────────────────
// Signal row (non-DataGrid, works for both fetched + streaming)
// ─────────────────────────────────────────────────────────────────────────────

function SignalRow({ signal, expanded, onToggle }: {
  signal: Signal;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "32px 130px 140px 100px 90px 80px 56px 60px",
          alignItems: "center",
          gap: 1,
          px: 1,
          py: 0.75,
          borderBottom: expanded ? "none" : "1px solid rgba(255,255,255,0.04)",
          "&:hover": { bgcolor: "rgba(255,255,255,0.025)" },
          cursor: "default",
        }}
      >
        <IconButton size="small" onClick={onToggle} sx={{ p: 0.3 }}>
          {expanded ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
        </IconButton>

        {/* Symbol */}
        <Box>
          <Typography variant="body2" fontWeight={700} color="primary.light" lineHeight={1.2}>
            {signal.symbol}
          </Typography>
          {signal.company_name && (
            <Typography variant="caption" color="text.disabled" noWrap sx={{ display: "block", fontSize: "0.62rem" }}>
              {signal.company_name}
            </Typography>
          )}
        </Box>

        {/* Status chip */}
        <StatusChip category={signal.category} displayCategory={signal.display_category} />

        {/* GATE bar */}
        <GATEBar score={signal.gate_strength} />

        {/* Entry */}
        <Typography variant="body2" sx={{ fontSize: "0.78rem" }}>
          {signal.entry != null ? `₹${signal.entry.toLocaleString("en-IN")}` : "—"}
        </Typography>

        {/* SL */}
        <Typography variant="body2" color="error.light" sx={{ fontSize: "0.78rem" }}>
          {signal.stop_loss != null ? `₹${signal.stop_loss.toLocaleString("en-IN")}` : "—"}
        </Typography>

        {/* RR */}
        <Typography
          variant="body2"
          fontWeight={600}
          sx={{ fontSize: "0.78rem", color: (signal.rr_t1 ?? 0) >= 2 ? "success.main" : "text.primary" }}
        >
          {formatRR(signal.rr_t1)}
        </Typography>

        {/* TF — always Daily for this platform */}
        <Chip
          label="Daily"
          size="small"
          sx={{ fontSize: "0.62rem", height: 18, bgcolor: "rgba(99,102,241,0.12)", color: "#818cf8", border: "1px solid rgba(99,102,241,0.25)" }}
        />
      </Box>

      <Collapse in={expanded} unmountOnExit>
        <ExpandedDetail signal={signal} />
      </Collapse>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Column headers
// ─────────────────────────────────────────────────────────────────────────────

const HEADERS = ["", "Symbol", "Status", "GATE", "Entry", "SL", "RR", "Timeframe"] as const;
const GRID = "32px 130px 140px 100px 90px 80px 56px 60px";

function TableHeaders() {
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: GRID,
        gap: 1,
        px: 1,
        py: 0.6,
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        bgcolor: "rgba(0,0,0,0.15)",
      }}
    >
      {HEADERS.map((h) => (
        <Typography key={h} variant="caption" color="text.disabled" sx={{ fontSize: "0.7rem", fontWeight: 600 }}>
          {h}
        </Typography>
      ))}
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Public export
// ─────────────────────────────────────────────────────────────────────────────

interface SignalTableProps {
  signals: Signal[];
  loading?: boolean;
}

export function SignalTable({ signals, loading }: SignalTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggle = (id: string) =>
    setExpandedId((prev) => (prev === id ? null : id));

  if (loading) {
    return (
      <Box>
        <TableHeaders />
        {Array.from({ length: 5 }).map((_, i) => (
          <Box
            key={i}
            sx={{
              display: "grid",
              gridTemplateColumns: GRID,
              gap: 1,
              px: 1,
              py: 0.75,
              borderBottom: "1px solid rgba(255,255,255,0.04)",
            }}
          >
            {HEADERS.map((h) => (
              <Box
                key={h}
                sx={{
                  height: 14,
                  bgcolor: "rgba(255,255,255,0.06)",
                  borderRadius: 0.5,
                  animation: "pulse 1.5s ease-in-out infinite",
                  "@keyframes pulse": {
                    "0%, 100%": { opacity: 1 },
                    "50%": { opacity: 0.4 },
                  },
                }}
              />
            ))}
          </Box>
        ))}
      </Box>
    );
  }

  return (
    <Box>
      <TableHeaders />
      {signals.map((sig) => (
        <SignalRow
          key={sig.id}
          signal={sig}
          expanded={expandedId === sig.id}
          onToggle={() => toggle(sig.id)}
        />
      ))}
    </Box>
  );
}
