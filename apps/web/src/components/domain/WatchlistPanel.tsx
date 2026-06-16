"use client";
import { useState, useCallback, memo } from "react";
import {
  Box, Card, Typography, Chip, Tab, Tabs, IconButton, Collapse,
  Stack, Divider, Skeleton, Tooltip, CircularProgress,
  useTheme, useMediaQuery,
} from "@mui/material";
import {
  Delete, ExpandMore, ExpandLess, FiberManualRecord, TrendingUp,
} from "@mui/icons-material";
import { enqueueSnackbar } from "notistack";
import {
  useGetWatchlistQuery,
  useGetWatchlistItemHistoryQuery,
  useRemoveFromWatchlistMutation,
} from "@/store/api/watchlistApi";
import { GATEBar } from "@/components/ui/GATEBar";
import { StockLink } from "@/components/ui/StockLink";
import { EmptyState } from "@/components/ui/EmptyState";
import { WatchSetupLoader } from "@/components/domain/WatchSetupLoader";
import { fromWatchlistItem } from "@/lib/tradeSetup";
import { formatIST, formatPrice } from "@/lib/formatters";
import { STATUS_COLORS, GATE_COLOR } from "@/lib/constants";
import type { WatchlistItem, WatchlistHistoryEvent, WatchlistStatus } from "@/types/watchlist";

// ─────────────────────────────────────────────────────────────────────────────
// Status config
// ─────────────────────────────────────────────────────────────────────────────

type FilterTab = "all" | WatchlistStatus;

const STATUS_TABS: { value: FilterTab; label: string; color: string }[] = [
  { value: "all",           label: "All",           color: "#94a3b8"                },
  { value: "active",        label: "Watching",      color: STATUS_COLORS.WATCH      },
  { value: "buy_triggered", label: "Buy Triggered", color: STATUS_COLORS.INVESTMENT },
  { value: "target_hit",    label: "Target Hit",    color: STATUS_COLORS.POSITIONAL },
  { value: "sl_hit",        label: "Stop Loss Hit", color: GATE_COLOR.FAIL          },
  { value: "closed",        label: "Closed",        color: STATUS_COLORS.IGNORE     },
];

const STATUS_META: Record<WatchlistStatus, { label: string; color: string }> = {
  active:        { label: "Watching",      color: STATUS_COLORS.WATCH      },
  buy_triggered: { label: "Buy Triggered", color: STATUS_COLORS.INVESTMENT },
  target_hit:    { label: "Target Hit",    color: STATUS_COLORS.POSITIONAL },
  sl_hit:        { label: "Stop Loss Hit", color: GATE_COLOR.FAIL          },
  closed:        { label: "Closed",        color: STATUS_COLORS.IGNORE     },
};

const EVENT_LABEL: Record<string, string> = {
  added:         "Added to watchlist",
  status_change: "Status changed",
  gate_update:   "GATE score updated",
  removed:       "Removed",
};

// ─────────────────────────────────────────────────────────────────────────────
// History timeline
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

const WatchlistRow = memo(function WatchlistRow({ item }: { item: WatchlistItem }) {
  const [expanded, setExpanded] = useState(false);
  const [removeFromWatchlist, { isLoading: isRemoving }] = useRemoveFromWatchlistMutation();
  const meta = STATUS_META[item.status];

  const handleRemove = useCallback(async () => {
    try {
      await removeFromWatchlist(item.symbol).unwrap();
      enqueueSnackbar(`${item.symbol} removed from watchlist`, { variant: "info" });
    } catch {
      enqueueSnackbar("Remove failed", { variant: "error" });
    }
  }, [removeFromWatchlist, item.symbol]);

  const handleToggle = useCallback(() => setExpanded((p) => !p), []);

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
        <IconButton
          size="small"
          onClick={handleToggle}
          aria-label={expanded ? "Collapse watchlist details" : "Expand watchlist details"}
          aria-expanded={expanded}
          sx={{ p: 0.3 }}
        >
          {expanded ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
        </IconButton>

        <StockLink symbol={item.symbol} variant="body2" fontWeight={700} color="primary.light" noWrap />

        <Box>
          <Chip
            label={item.source === "scanner" ? "Scanner" : "Manual"}
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.62rem", height: 18, mr: 0.5 }}
          />
        </Box>

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

        <GATEBar score={item.gate_strength} />

        <Typography variant="caption" sx={{ fontSize: "0.75rem" }}>
          {formatPrice(item.entry)}
        </Typography>

        <Typography variant="caption" color="error.light" sx={{ fontSize: "0.75rem" }}>
          {formatPrice(item.stop_loss)}
        </Typography>

        <Tooltip title="Remove from watchlist">
          <span>
            <IconButton
              size="small"
              onClick={handleRemove}
              disabled={isRemoving}
              aria-label={`Remove ${item.symbol} from watchlist`}
              sx={{ p: 0.3 }}
            >
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
          {expanded && (
            <Box px={2} pb={1}>
              <WatchSetupLoader
                symbol={item.symbol}
                category="WATCH"
                initialSetup={fromWatchlistItem(item)}
                variant="compact"
                headerTitle="Trade Setup"
              />
            </Box>
          )}
          <Divider sx={{ borderColor: "rgba(255,255,255,0.04)" }} />
          <HistoryTimeline symbol={item.symbol} />
        </Box>
      </Collapse>
    </>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Mobile card row (replaces grid row on xs screens)
// ─────────────────────────────────────────────────────────────────────────────

const WatchlistMobileRow = memo(function WatchlistMobileRow({ item }: { item: WatchlistItem }) {
  const [expanded, setExpanded] = useState(false);
  const [removeFromWatchlist, { isLoading: isRemoving }] = useRemoveFromWatchlistMutation();
  const meta = STATUS_META[item.status];

  const handleRemove = useCallback(async () => {
    try {
      await removeFromWatchlist(item.symbol).unwrap();
      enqueueSnackbar(`${item.symbol} removed from watchlist`, { variant: "info" });
    } catch {
      enqueueSnackbar("Remove failed", { variant: "error" });
    }
  }, [removeFromWatchlist, item.symbol]);

  return (
    <>
      <Box
        onClick={() => setExpanded((p) => !p)}
        sx={{
          px: 1.5, py: 1.25,
          borderBottom: expanded ? "none" : "1px solid rgba(255,255,255,0.04)",
          cursor: "pointer",
          WebkitTapHighlightColor: "transparent",
          "&:active": { bgcolor: "rgba(255,255,255,0.04)" },
        }}
      >
        {/* Top row: symbol + status + actions */}
        <Box display="flex" alignItems="center" gap={0.75} mb={0.6}>
          <StockLink symbol={item.symbol} variant="body2" fontWeight={700} color="primary.light" noWrap sx={{ flex: 1, minWidth: 0 }} />
          <Chip
            label={meta.label}
            size="small"
            sx={{ bgcolor: `${meta.color}1a`, color: meta.color, border: `1px solid ${meta.color}40`, fontWeight: 600, fontSize: "0.62rem", height: 18, flexShrink: 0 }}
          />
          <Tooltip title="Remove from watchlist">
            <span>
              <IconButton
                size="small"
                onClick={(e) => { e.stopPropagation(); handleRemove(); }}
                disabled={isRemoving}
                aria-label={`Remove ${item.symbol} from watchlist`}
                sx={{ p: 0.3, flexShrink: 0 }}
              >
                {isRemoving
                  ? <CircularProgress size={14} sx={{ color: "error.dark" }} />
                  : <Delete sx={{ color: "error.dark", fontSize: 16 }} />}
              </IconButton>
            </span>
          </Tooltip>
          {expanded
            ? <ExpandLess sx={{ color: "text.disabled", fontSize: 16, flexShrink: 0 }} />
            : <ExpandMore sx={{ color: "text.disabled", fontSize: 16, flexShrink: 0 }} />}
        </Box>

        {/* Bottom row: GATE + prices + source */}
        <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
          <Box sx={{ minWidth: 80, flex: "1 1 90px" }}>
            <GATEBar score={item.gate_strength} />
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.7rem" }}>
            Entry: {formatPrice(item.entry)}
          </Typography>
          <Typography variant="caption" color="error.light" sx={{ fontSize: "0.7rem" }}>
            SL: {formatPrice(item.stop_loss)}
          </Typography>
          <Chip
            label={item.source === "scanner" ? "Scanner" : "Manual"}
            size="small" variant="outlined"
            sx={{ fontSize: "0.58rem", height: 16, ml: "auto" }}
          />
        </Box>
      </Box>

      <Collapse in={expanded} unmountOnExit>
        <Box sx={{ bgcolor: "rgba(99,102,241,0.04)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <Box px={1.5} pt={1} pb={0.5}>
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.7rem" }}>
              Added: {formatIST(item.added_at)}
              {item.last_checked_at && ` · Last checked: ${formatIST(item.last_checked_at)}`}
            </Typography>
          </Box>
          {expanded && (
            <Box px={1.5} pb={1}>
              <WatchSetupLoader
                symbol={item.symbol}
                category="WATCH"
                initialSetup={fromWatchlistItem(item)}
                variant="compact"
                headerTitle="Trade Setup"
              />
            </Box>
          )}
          <Divider sx={{ borderColor: "rgba(255,255,255,0.04)" }} />
          <HistoryTimeline symbol={item.symbol} />
        </Box>
      </Collapse>
    </>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Table column headers
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
// Public panel — embedded inside the scanner page Watchlist tab
// ─────────────────────────────────────────────────────────────────────────────

export function WatchlistPanel() {
  const theme    = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const { data: allItems, isLoading } = useGetWatchlistQuery({});

  const items = activeTab === "all"
    ? (allItems ?? [])
    : (allItems ?? []).filter((i) => i.status === activeTab);

  const counts: Record<string, number> = {};
  for (const item of (allItems ?? [])) {
    counts[item.status] = (counts[item.status] ?? 0) + 1;
  }

  return (
    <Card>
      {/* Status filter tabs */}
      <Box sx={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <Tabs
          value={activeTab}
          onChange={(_, v) => setActiveTab(v)}
          variant="scrollable"
          scrollButtons="auto"
          allowScrollButtonsMobile
          sx={{
            minHeight: 42,
            "& .MuiTab-root": { minHeight: 42, fontSize: "0.78rem", px: { xs: 1, sm: 1.5 } },
            "& .MuiTabs-scrollButtons": { color: "text.secondary" },
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

      {/* Rows */}
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
          {!isMobile && <TableHeaders />}
          {items.map((item) =>
            isMobile ? (
              <WatchlistMobileRow key={item.id} item={item} />
            ) : (
              <WatchlistRow key={item.id} item={item} />
            )
          )}
        </>
      )}
    </Card>
  );
}
