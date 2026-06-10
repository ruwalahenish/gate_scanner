"use client";
import { Card, CardContent, Skeleton, Box, type SxProps } from "@mui/material";
import { memo } from "react";

// Column widths matching SignalTable's CSS grid for content-shaped loading placeholders.
const SIGNAL_ROW_WIDTHS = [32, 130, 140, 100, 90, 80, 56, 60];

type SkeletonVariant = "card" | "stat" | "table-row" | "signal-row";

interface SkeletonCardProps {
  rows?: number;
  height?: number;
  sx?: SxProps;
  variant?: SkeletonVariant;
}

export const SkeletonCard = memo(function SkeletonCard({
  rows = 3, height, sx, variant = "card",
}: SkeletonCardProps) {
  if (variant === "stat") {
    return (
      <Card sx={sx}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="flex-start">
            <Box flex={1}>
              <Skeleton variant="text" width="50%" height={14} sx={{ mb: 0.5 }} />
              <Skeleton variant="text" width="65%" height={36} sx={{ mb: 0.5 }} />
              <Skeleton variant="text" width="40%" height={12} />
            </Box>
            <Skeleton variant="circular" width={28} height={28} />
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (variant === "table-row") {
    return (
      <Box
        sx={{
          display: "flex",
          gap: 2,
          px: 1.5,
          py: 0.75,
          borderBottom: "1px solid rgba(255,255,255,0.04)",
          ...sx,
        }}
      >
        {[80, 120, 160, 80, 80, 70].map((w, i) => (
          <Skeleton key={i} variant="rectangular" width={w} height={14} sx={{ borderRadius: 0.5 }} />
        ))}
      </Box>
    );
  }

  if (variant === "signal-row") {
    return (
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: SIGNAL_ROW_WIDTHS.map(w => `${w}px`).join(" "),
          gap: "8px",
          px: 1,
          py: 0.75,
          borderBottom: "1px solid rgba(255,255,255,0.04)",
          alignItems: "center",
          ...sx,
        }}
      >
        {SIGNAL_ROW_WIDTHS.map((w, i) => (
          <Skeleton key={i} variant="rectangular" width={w - 4} height={14} sx={{ borderRadius: 0.5 }} />
        ))}
      </Box>
    );
  }

  // Default "card" variant
  if (height) {
    return (
      <Card sx={sx}>
        <CardContent>
          <Skeleton variant="rectangular" height={height} sx={{ borderRadius: 1 }} />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={sx}>
      <CardContent>
        <Skeleton variant="text" width="40%" sx={{ mb: 1 }} />
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} variant="text" width={i === rows - 1 ? "60%" : "100%"} />
        ))}
      </CardContent>
    </Card>
  );
});

export const SkeletonStat = memo(function SkeletonStat({ sx }: { sx?: SxProps }) {
  return (
    <Box sx={sx}>
      <Skeleton variant="text" width={60} height={14} />
      <Skeleton variant="text" width={40} height={36} />
    </Box>
  );
});
