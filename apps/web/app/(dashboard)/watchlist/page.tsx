"use client";
import { useState } from "react";
import {
  Box, Card, Typography, Chip, Tab, Tabs, IconButton, Collapse,
  Stack, Divider, Skeleton, Tooltip, CircularProgress,
} from "@mui/material";
import {
  Delete, ExpandMore, ExpandLess,
  FiberManualRecord, TrendingUp, GpsFixed, Block, CheckCircle,
} from "@mui/icons-material";
import { enqueueSnackbar } from "notistack";
import {
  useGetWatchlistQuery,
  useGetWatchlistItemHistoryQuery,
  useRemoveFromWatchlistMutation,
} from "@/store/api/watchlistApi";
import { GATEBar } from "@/components/ui/GATEBar";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatIST, formatPrice } from "@/lib/formatters";
import type { WatchlistItem, WatchlistHistoryEvent, WatchlistStatus } from "@/types/watchlist";

// ─────────────────────────────────────────────────────────────────────────────
// Status config
// ─────────────────────────────────────────────────────────────────────────────

type FilterTab = "all" | WatchlistStatus;

const STATUS_TABS: { value: FilterTab; label: string; color: string }[] = [
  { value: "all",           label: "All",           color: "#94a3b8" },
  { value: "active",        label: "Watching",      color: "#f59e0b" },
  { value: "buy_triggered", label: "Buy Triggered", color: "#22c55e" },
  { value: "target_hit",    label: "Target Hit",    color: "#38bdf8" },
  { value: "sl_hit",        label: "Stop Loss Hit", color: "#ef4444" },
  { value: "closed",        label: "Closed",        color: "#64748b" },
];

const STATUS_META: Record<WatchlistStatus, { label: string; color: string }> = {
  active:        { label: "Watching",      color: "#f59e0b" },
  buy_triggered: { label: "Buy Triggered", color: "#22c55e" },
  target_hit:    { label: "Target Hit",    color: "#38bdf8" },
  sl_hit:        { label: "Stop Loss Hit", color: "#ef4444" },
  closed:        { label: "Closed",        color: "#64748b" },
};

const EVENT_LABEL: Record<string, string> = {
  added:         "Added to watchlist",
  status_change: "Status changed",
  gate_update:   "GATE score updated",
  removed:       "Removed",
};

// ─────────────────────────────────────────────────────────────────────────────
// History timeline — lazy-loaded on expand
// ─────────────────────────────────────────────────────────────────────────────

function HistoryTimeline({ symbol }: { symbol: string }) {
  const { data: events, isLoading } = useGetWatchlistItemHistoryQuery(symbol);

  if (isLoading) {
    return (
      <Box px={2} py={1}>
        {[1, 2, 3].map((i) => <Skeleton key={i} height={22} sx={{ mb: 0.4 }} />)}
      </Box>
    );
  }
  if (!events || events.length === 0) {
    return (
      <Box px={2} py={1}>
        <Typography variant="caption" color="text.disabled">No history recorded.</Typography>
      </Box>
    );
  }

  return (
    <Box px={2} py={1}>
      <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.8}>
        HISTORY
      </Typography>
      <Stack spacing={0.5}>
        {events.map((ev: WatchlistHistoryEvent) => {
          const toMeta = ev.to_status ? STATUS_META[ev.to_status] : null;
          return (
            <Box key={ev.id} display="flex" alignItems="flex-start" gap={1}>
              <FiberManualRecord sx={{ fontSize: 8, color: toMeta?.color ?? "text.disabled", mt: 0.6 }} />
              <Box flex={1}>
                <Typography variant="caption" sx={{ fontSize: "0.72rem" }}>
                  {EVENT_LABEL[ev.event] ?? ev.event}
                  {ev.to_status && toMeta && (
                    <span style={{ color: toMeta.color, fontWeight: 600 }}>
                      {" → "}{toMeta.label}
                    </span>
                  )}
                  {ev.event === "gate_update" && ev.details?.gate_strength != null && (
                    <span style={{ color: "#94a3b8" }}>
                      {" "}(GATE: {(ev.details.gate_strength as number).toFixed(0)})
                    </span>
                  )}
                </Typography>
                <Typography variant="caption" color="text.disabled" display="block" sx={{ fontSize: "0.65rem" }}>
                  {formatIST(ev.occurred_at)}
                </Typography>
              </Box>
            </Box>
          );
        })}
      </Stack>
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Watchlist row
// ─────────────────────────────────────────────────────────────────────────────

const GRID = "32px 110px 1fr 130px 90px 85px 85px 36px";

function WatchlistRow({ item }: { item: WatchlistItem }) {
  const [expanded, setExpanded] = useState(false);
  const [removeFromWatchlist, { isLoading: isRemoving }] = useRemoveFromWatchlistMutation();
  const meta = STATUS_META[item.status];

  const handleRemove = async () => {
    try {
      await removeFromWatchlist(item.symbol).unwrap();
      enqueueSnackbar(`${item.symbol} removed from watchlist`, { variant: "info" });
    } catch {
      enqueueSnackbar("Remove failed", { variant: "error" });
    }
  };

  return (
    <>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: GRID,
          alignItems: "center",
          gap: 1,
          px: 1,
          py: 0.85,
          borderBottom: expanded ? "none" : "1px solid rgba(255,255,255,0.04)",
          "&:hover": { bgcolor: "rgba(255,255,255,0.02)" },
        }}
      >
        {/* Expand toggle */}
        <IconButton size="small" onClick={() => setExpanded((p) => !p)} sx={{ p: 0.3 }}>
          {expanded ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
        </IconButton>

        {/* Symbol */}
        <Typography variant="body2" fontWeight={700} color="primary.light" noWrap>
          {item.symbol}
        </Typography>

        {/* Source badge */}
        <Box>
          <Chip
            label={item.source === "scanner" ? "Scanner" : "Manual"}
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.62rem", height: 18, mr: 0.5 }}
          />
        </Box>

        {/* Status chip */}
        <Chip
          label={meta.label}
          size="small"
          sx={{
            bgcolor: `${meta.color}1a`,
            color: meta.color,
            border: `1px solid ${meta.color}40`,
            fontWeight: 600,
            fontSize: "0.65rem",
            height: 20,
          }}
        />

        {/* GATE score */}
        <GATEBar score={item.gate_strength} />

        {/* Entry */}
        <Typography variant="caption" sx={{ fontSize: "0.75rem" }}>
          {item.entry != null ? `₹${item.entry.toLocaleString("en-IN")}` : "—"}
        </Typography>

        {/* SL */}
        <Typography variant="caption" color="error.light" sx={{ fontSize: "0.75rem" }}>
          {item.stop_loss != null ? `₹${item.stop_loss.toLocaleString("en-IN")}` : "—"}
        </Typography>

        {/* Remove */}
        <Tooltip title="Remove from watchlist">
          <span>
            <IconButton size="small" onClick={handleRemove} disabled={isRemoving} sx={{ p: 0.3 }}>
              {isRemoving
                ? <CircularProgress size={14} sx={{ color: "error.dark" }} />
                : <Delete fontSize="small" sx={{ color: "error.dark", fontSize: 16 }} />}
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      <Collapse in={expanded} unmountOnExit>
        <Box sx={{ bgcolor: "rgba(99,102,241,0.04)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <Box px={2} pt={1} pb={0.5}>
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.7rem" }}>
              Added: {formatIST(item.added_at)}
              {item.last_checked_at && ` · Last checked: ${formatIST(item.last_checked_at)}`}
            </Typography>
          </Box>
          <Divider sx={{ borderColor: "rgba(255,255,255,0.04)" }} />
          <HistoryTimeline symbol={item.symbol} />
        </Box>
      </Collapse>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Table headers
// ─────────────────────────────────────────────────────────────────────────────

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
      {["", "Symbol", "Source", "Status", "GATE", "Entry", "SL", ""].map((h) => (
        <Typography key={h} variant="caption" color="text.disabled" sx={{ fontSize: "0.7rem", fontWeight: 600 }}>
          {h}
        </Typography>
      ))}
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

export default function WatchlistPage() {
  const [activeTab, setActiveTab] = useState<FilterTab>("all");

  const { data: allItems, isLoading } = useGetWatchlistQuery({});

  // Filter by tab
  const items = activeTab === "all"
    ? (allItems ?? [])
    : (allItems ?? []).filter((i) => i.status === activeTab);

  // Count by status for badges
  const counts: Record<string, number> = {};
  for (const item of (allItems ?? [])) {
    counts[item.status] = (counts[item.status] ?? 0) + 1;
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" alignItems="baseline" gap={1} mb={2}>
        <Typography variant="h6" fontWeight={700}>Watchlist</Typography>
        {allItems && (
          <Typography variant="caption" color="text.secondary">
            {allItems.length} stocks · auto-managed by GATE Scanner
          </Typography>
        )}
      </Box>

      <Card>
        {/* Status filter tabs */}
        <Box sx={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <Tabs
            value={activeTab}
            onChange={(_, v) => setActiveTab(v)}
            variant="scrollable"
            scrollButtons="auto"
            sx={{
              minHeight: 42,
              "& .MuiTab-root": { minHeight: 42, fontSize: "0.78rem", px: 1.5 },
            }}
          >
            {STATUS_TABS.map(({ value, label, color }) => {
              const count = value === "all" ? (allItems?.length ?? 0) : (counts[value] ?? 0);
              return (
                <Tab
                  key={value}
                  value={value}
                  label={
                    <Box display="flex" alignItems="center" gap={0.6}>
                      <span>{label}</span>
                      <Chip
                        label={count}
                        size="small"
                        sx={{
                          height: 17,
                          fontSize: "0.62rem",
                          bgcolor: activeTab === value ? `${color}30` : "rgba(255,255,255,0.06)",
                          color: activeTab === value ? color : "text.secondary",
                          fontWeight: 600,
                        }}
                      />
                    </Box>
                  }
                />
              );
            })}
          </Tabs>
        </Box>

        {/* Table */}
        {isLoading ? (
          <Box px={2} py={2}>
            {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} height={40} sx={{ mb: 0.5 }} />)}
          </Box>
        ) : items.length === 0 ? (
          <EmptyState
            icon={activeTab === "all" ? <TrendingUp /> : undefined}
            title={
              activeTab === "all"
                ? "Watchlist is empty"
                : `No stocks with status "${STATUS_META[activeTab as WatchlistStatus]?.label ?? activeTab}"`
            }
            description={
              activeTab === "all"
                ? "Stocks are automatically added when the GATE Scanner detects WATCH opportunities"
                : "Try a different filter or run a new scan"
            }
          />
        ) : (
          <>
            <TableHeaders />
            {items.map((item) => (
              <WatchlistRow key={item.id} item={item} />
            ))}
          </>
        )}
      </Card>
    </Box>
  );
}
