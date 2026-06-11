"use client";
import { memo } from "react";
import {
  Box, Paper, Grid, Typography, Divider, LinearProgress, Chip,
  Button, Alert, CircularProgress, Skeleton, Tooltip,
} from "@mui/material";
import {
  CheckCircle, Cancel, TrendingUp, TrendingDown, Bolt, Visibility,
} from "@mui/icons-material";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { GATEChart } from "@/components/domain/GATEChart";
import { formatPrice, formatRR, formatScore } from "@/lib/formatters";
import { STATUS_COLORS, GATE_COLOR, GATE_THRESHOLDS } from "@/lib/constants";
import { toChartLevels, type TradeSetup } from "@/lib/tradeSetup";
import type { Bar } from "@/types/stock";

// ─────────────────────────────────────────────────────────────────────────────
// Shared primitives (single source — re-imported by SignalTable & detail page)
// ─────────────────────────────────────────────────────────────────────────────

export const LevelRow = memo(function LevelRow({
  label, value, color, muted = false,
}: { label: string; value: number | null; color?: string; muted?: boolean }) {
  return (
    <Box display="flex" justifyContent="space-between" alignItems="center" py={0.4}>
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.72rem" }}>{label}</Typography>
      <Typography
        variant="body2"
        fontWeight={600}
        sx={{
          color: value == null ? "text.disabled" : (color ?? "text.primary"),
          fontVariantNumeric: "tabular-nums",
          opacity: muted ? 0.7 : 1,
        }}
      >
        {value != null ? formatPrice(value) : "—"}
      </Typography>
    </Box>
  );
});

export const ScoreBar = memo(function ScoreBar({
  label, value,
}: { label: string; value: number | null | undefined }) {
  const v = value ?? 0;
  const pct = Math.min(100, Math.max(0, v));
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
          height: 3, borderRadius: 2, bgcolor: "rgba(255,255,255,0.06)",
          "& .MuiLinearProgress-bar": { bgcolor: color, borderRadius: 2 },
        }}
      />
    </Box>
  );
});

export const BoolFlag = memo(function BoolFlag({
  val, label,
}: { val: boolean | null | undefined; label: string }) {
  const ok = val === true;
  return (
    <Box display="flex" alignItems="center" gap={0.6} mb={0.4}>
      {ok
        ? <CheckCircle sx={{ fontSize: 13, color: "success.main" }} aria-hidden="true" />
        : <Cancel sx={{ fontSize: 13, color: val === false ? "error.main" : "text.disabled" }} aria-hidden="true" />}
      <Typography variant="caption" color={ok ? "text.primary" : "text.disabled"} sx={{ fontSize: "0.7rem" }}>
        {label}
      </Typography>
    </Box>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Decision strip — the prominent "should I buy now?" summary
// ─────────────────────────────────────────────────────────────────────────────

function DecisionStat({
  label, value, color, hint,
}: { label: string; value: string; color: string; hint?: string }) {
  const inner = (
    <Box
      sx={{
        flex: 1, minWidth: 96, py: 1, px: 1.5, borderRadius: 1.5,
        bgcolor: `${color}0d`, border: `1px solid ${color}30`,
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.62rem" }}>{label}</Typography>
      <Typography variant="subtitle2" fontWeight={700} sx={{ color, fontVariantNumeric: "tabular-nums", lineHeight: 1.3 }}>
        {value}
      </Typography>
    </Box>
  );
  return hint ? <Tooltip title={hint}>{inner}</Tooltip> : inner;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main panel
// ─────────────────────────────────────────────────────────────────────────────

interface TradeSetupPanelProps {
  setup: TradeSetup | null;
  variant?: "full" | "compact";
  showChart?: boolean;
  chartBars?: Bar[];
  chartLoading?: boolean;
  loading?: boolean;        // on-demand analysis in flight
  error?: string | null;
  onRetry?: () => void;
  /** Show a primary "Load trade setup" CTA when levels haven't been computed yet. */
  onLoadSetup?: () => void;
  headerTitle?: string;
  elevation?: number;
}

const PAPER_SX = {
  p: 2,
  bgcolor: "rgba(99,102,241,0.05)",
  border: "1px solid rgba(99,102,241,0.15)",
  borderRadius: 2,
} as const;

export const TradeSetupPanel = memo(function TradeSetupPanel({
  setup,
  variant = "full",
  showChart = false,
  chartBars,
  chartLoading = false,
  loading = false,
  error = null,
  onRetry,
  onLoadSetup,
  headerTitle = "Trade Setup",
}: TradeSetupPanelProps) {
  // ── Loading (analysis in flight) ───────────────────────────────────────────
  if (loading) {
    return (
      <Paper elevation={0} sx={PAPER_SX}>
        <Box display="flex" alignItems="center" gap={1.5} mb={1.5}>
          <CircularProgress size={16} thickness={5} />
          <Typography variant="subtitle2" fontWeight={700}>Running GATE engine…</Typography>
          <Typography variant="caption" color="text.disabled">~5s</Typography>
        </Box>
        <Skeleton variant="rounded" height={48} sx={{ mb: 1 }} />
        <Skeleton variant="text" width="60%" />
        <Skeleton variant="text" width="80%" />
        <Skeleton variant="text" width="45%" />
      </Paper>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <Alert
        severity="error"
        action={onRetry && <Button color="inherit" size="small" onClick={onRetry}>Retry</Button>}
        sx={{ borderRadius: 2 }}
      >
        {error}
      </Alert>
    );
  }

  if (!setup) return null;

  const isAnticipated = setup.provenance === "anticipated";
  const isNone = setup.provenance === "none";
  const watchColor = STATUS_COLORS.WATCH;

  // ── "Anticipated, not loaded yet" → CTA to compute levels on demand ─────────
  if (!setup.hasLevels && isAnticipated && onLoadSetup) {
    return (
      <Paper elevation={0} sx={PAPER_SX}>
        <Box display="flex" alignItems="center" justifyContent="space-between" gap={1.5} flexWrap="wrap">
          <Box display="flex" alignItems="center" gap={1}>
            <Visibility sx={{ fontSize: 18, color: watchColor }} />
            <Box>
              <Typography variant="subtitle2" fontWeight={700}>Watching for breakout</Typography>
              <Typography variant="caption" color="text.secondary">
                {setup.gateStrength != null ? `GATE ${setup.gateStrength.toFixed(0)} · ` : ""}
                Compute the anticipated entry, stop loss & targets from the live engine.
              </Typography>
            </Box>
          </Box>
          <Button variant="contained" size="small" startIcon={<Bolt />} onClick={onLoadSetup}>
            Load trade setup
          </Button>
        </Box>
      </Paper>
    );
  }

  // ── "No qualifying setup yet" (live analysis returned no signal) ────────────
  if (isNone) {
    return (
      <Paper elevation={0} sx={PAPER_SX}>
        <Box display="flex" alignItems="center" gap={1} mb={1}>
          <Visibility sx={{ fontSize: 18, color: watchColor }} />
          <Typography variant="subtitle2" fontWeight={700}>No qualifying setup yet — watching for breakout</Typography>
        </Box>
        <Box sx={{ maxWidth: 360 }}>
          <ScoreBar label="GATE Score" value={setup.gateStrength} />
          <ScoreBar label="MTF Alignment" value={setup.mtfAlignmentPct} />
          <ScoreBar label="Structure Quality" value={setup.structureQuality} />
        </Box>
        {setup.reasoning && (
          <>
            <Divider sx={{ borderColor: "rgba(255,255,255,0.06)", my: 1 }} />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.72rem", lineHeight: 1.6 }}>
              {setup.reasoning}
            </Typography>
          </>
        )}
      </Paper>
    );
  }

  // ── Full setup ──────────────────────────────────────────────────────────────
  const SideIcon = setup.side === "SELL" ? TrendingDown : TrendingUp;
  const sideColor = setup.side === "SELL" ? GATE_COLOR.FAIL : STATUS_COLORS.INVESTMENT;
  const rr1 = setup.rr.t1;
  const colWidth = variant === "compact" ? 12 : 4;

  const chart = showChart && chartBars ? (
    <Box sx={{ borderRadius: 1.5, overflow: "hidden", mb: 1.5 }}>
      <GATEChart bars={chartBars} signal={toChartLevels(setup)} loading={chartLoading} height={240} />
    </Box>
  ) : null;

  return (
    <Paper elevation={0} sx={PAPER_SX}>
      {/* Header */}
      <Box display="flex" alignItems="center" gap={1} mb={1.5} flexWrap="wrap">
        <Typography variant="subtitle2" fontWeight={700}>{headerTitle}</Typography>
        {setup.category && <CategoryChip category={setup.category} chipSize="xs" />}
        {setup.side && <SideIcon sx={{ fontSize: 17, color: sideColor }} aria-label={setup.side} />}
        {isAnticipated && (
          <Chip
            label="Anticipated — not yet triggered"
            size="small"
            sx={{
              height: 18, fontSize: "0.62rem", fontWeight: 600,
              bgcolor: `${watchColor}1f`, color: watchColor, border: `1px solid ${watchColor}40`,
            }}
          />
        )}
      </Box>

      {chart}

      {/* Decision strip */}
      <Box display="flex" gap={1} flexWrap="wrap" mb={1.5}>
        <DecisionStat label="Entry" value={formatPrice(setup.entry)} color={STATUS_COLORS.SWING} />
        <DecisionStat
          label="Stop Loss"
          value={formatPrice(setup.stopLoss)}
          color={GATE_COLOR.FAIL}
          hint={setup.slDistancePct != null ? `SL distance ${setup.slDistancePct.toFixed(1)}%` : undefined}
        />
        <DecisionStat
          label="Risk : Reward (T1)"
          value={formatRR(rr1)}
          color={rr1 != null && rr1 >= 2 ? GATE_COLOR.HIGH : "#94a3b8"}
          hint="Reward to risk at Target 1"
        />
        <DecisionStat
          label="Confidence"
          value={setup.confidence != null ? formatScore(setup.confidence) : formatScore(setup.gateStrength)}
          color={STATUS_COLORS.POSITIONAL}
          hint={setup.confidence != null ? "Signal confidence" : "GATE strength (no confidence score)"}
        />
      </Box>

      <Grid container spacing={2}>
        {/* Levels */}
        <Grid item xs={12} sm={colWidth}>
          <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" mb={0.6}>
            LEVELS
          </Typography>
          <LevelRow label="Entry" value={setup.entry} color={STATUS_COLORS.SWING} muted={isAnticipated} />
          <LevelRow label="Stop Loss" value={setup.stopLoss} color={GATE_COLOR.FAIL} muted={isAnticipated} />
          <LevelRow label="Target 1" value={setup.targets.t1} color="success.light" muted={isAnticipated} />
          <LevelRow label="Target 2" value={setup.targets.t2} color={STATUS_COLORS.INVESTMENT} muted={isAnticipated} />
          <LevelRow label="Target 3" value={setup.targets.t3} color="success.dark" muted={isAnticipated} />
        </Grid>

        {/* Scores */}
        <Grid item xs={12} sm={colWidth}>
          <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" mb={0.6}>
            SCORES
          </Typography>
          <ScoreBar label="GATE Score" value={setup.gateStrength} />
          <ScoreBar label="Confidence" value={setup.confidence} />
          <ScoreBar label="Structure Quality" value={setup.structureQuality} />
          <ScoreBar label="MTF Alignment" value={setup.mtfAlignmentPct} />
          <ScoreBar label="Breakout Prob" value={setup.breakoutProbability} />
          <ScoreBar label="Vol Compression" value={setup.volatilityCompression} />
        </Grid>

        {/* Confirmation signals + details */}
        <Grid item xs={12} sm={colWidth}>
          <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" mb={0.6}>
            CONFIRMATION
          </Typography>
          <BoolFlag val={setup.flags.htfConfirmed} label="HTF Confirmed" />
          <BoolFlag val={setup.flags.correctionValidated} label="Correction Validated" />
          <BoolFlag val={setup.flags.bounceSequenceValid} label="Bounce Sequence" />
          <BoolFlag val={setup.flags.fibConfluence} label="Fib Confluence" />
          <Box mt={0.8}>
            {[
              ["Signal TF", setup.signalTimeframe],
              ["SL TF", setup.slTimeframe],
              ["Trend", setup.trendDirection],
              ["Phase", setup.phase],
            ].map(([label, val]) => (
              <Box key={String(label)} display="flex" justifyContent="space-between" mb={0.3}>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.7rem" }}>{label}</Typography>
                <Typography variant="caption" fontWeight={500} sx={{ fontSize: "0.7rem" }}>{val ?? "—"}</Typography>
              </Box>
            ))}
          </Box>
        </Grid>

        {/* Reasoning */}
        {setup.reasoning && (
          <Grid item xs={12}>
            <Divider sx={{ borderColor: "rgba(255,255,255,0.06)", mb: 1 }} />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.72rem", lineHeight: 1.6 }}>
              {setup.reasoning}
            </Typography>
          </Grid>
        )}
      </Grid>

      {onRetry && (
        <Box mt={1.5} display="flex" justifyContent="flex-end">
          <Button size="small" onClick={onRetry}>Re-run analysis</Button>
        </Box>
      )}
    </Paper>
  );
});
