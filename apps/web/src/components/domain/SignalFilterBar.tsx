"use client";
import {
  Box, FormControl, InputLabel, Select, MenuItem,
  Slider, Typography, Chip, Stack,
} from "@mui/material";
import { CATEGORY_ORDER, CATEGORY_COLORS } from "@/lib/constants";
import type { SignalFilters, SignalCategory } from "@/types/signal";

interface Props {
  filters: SignalFilters;
  onChange: (f: Partial<SignalFilters>) => void;
}

const TIMEFRAMES = ["1m", "5m", "15m", "30m", "60m", "4h", "1d", "1wk", "1mo"];

export function SignalFilterBar({ filters, onChange }: Props) {
  return (
    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5, alignItems: "center", mb: 2 }}>
      {/* Category toggle chips */}
      <Stack direction="row" spacing={0.5} flexWrap="wrap">
        <Chip
          label="All"
          size="small"
          onClick={() => onChange({ category: undefined })}
          variant={!filters.category ? "filled" : "outlined"}
          sx={{ cursor: "pointer" }}
        />
        {CATEGORY_ORDER.filter((c) => c !== "IGNORE").map((cat) => (
          <Chip
            key={cat}
            label={cat}
            size="small"
            onClick={() => onChange({ category: cat === filters.category ? undefined : cat as SignalCategory })}
            variant={filters.category === cat ? "filled" : "outlined"}
            sx={{
              cursor: "pointer",
              borderColor: CATEGORY_COLORS[cat as SignalCategory],
              color: CATEGORY_COLORS[cat as SignalCategory],
              "&.MuiChip-filled": {
                bgcolor: `${CATEGORY_COLORS[cat as SignalCategory]}25`,
              },
            }}
          />
        ))}
      </Stack>

      {/* Timeframe */}
      <FormControl size="small" sx={{ minWidth: 90 }}>
        <InputLabel>Timeframe</InputLabel>
        <Select
          value={filters.timeframe ?? ""}
          label="Timeframe"
          onChange={(e) => onChange({ timeframe: (e.target.value as string) || undefined })}
        >
          <MenuItem value="">All</MenuItem>
          {TIMEFRAMES.map((tf) => (
            <MenuItem key={tf} value={tf}>{tf}</MenuItem>
          ))}
        </Select>
      </FormControl>

      {/* Side */}
      <FormControl size="small" sx={{ minWidth: 80 }}>
        <InputLabel>Side</InputLabel>
        <Select
          value={filters.side ?? ""}
          label="Side"
          onChange={(e) => onChange({ side: (e.target.value as "BUY" | "SELL") || undefined })}
        >
          <MenuItem value="">Both</MenuItem>
          <MenuItem value="BUY">BUY</MenuItem>
          <MenuItem value="SELL">SELL</MenuItem>
        </Select>
      </FormControl>

      {/* Min GATE score */}
      <Box sx={{ minWidth: 140, px: 1 }}>
        <Typography variant="caption" color="text.secondary">
          Min GATE: {filters.min_gate ?? 0}
        </Typography>
        <Slider
          size="small"
          value={filters.min_gate ?? 0}
          min={0}
          max={90}
          step={5}
          onChange={(_, v) => onChange({ min_gate: v as number })}
          sx={{ mt: -0.5 }}
        />
      </Box>
    </Box>
  );
}
