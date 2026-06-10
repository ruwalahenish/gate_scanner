"use client";
import { Box, Typography, type TypographyProps } from "@mui/material";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import { formatPct, formatPrice } from "@/lib/formatters";
import { memo } from "react";

interface PnlBadgeProps extends Omit<TypographyProps, "color"> {
  pnl: number | null | undefined;
  pnlPct?: number | null;
  showAbs?: boolean;
  showIcon?: boolean;
}

export const PnlBadge = memo(function PnlBadge({
  pnl, pnlPct, showAbs = true, showIcon = false, ...props
}: PnlBadgeProps) {
  if (pnl == null) return <Typography {...props} color="text.disabled">—</Typography>;
  const isPositive = pnl >= 0;
  const color = isPositive ? "success.main" : "error.main";

  if (showIcon) {
    return (
      <Box display="flex" alignItems="center" gap={0.3}>
        {isPositive
          ? <TrendingUpIcon sx={{ fontSize: 14, color }} />
          : <TrendingDownIcon sx={{ fontSize: 14, color }} />}
        <Typography {...props} sx={{ color, fontWeight: 600, ...props.sx }}>
          {showAbs && formatPrice(pnl)}
          {pnlPct != null && ` (${formatPct(pnlPct)})`}
          {!showAbs && pnlPct != null && formatPct(pnlPct)}
        </Typography>
      </Box>
    );
  }

  return (
    <Typography {...props} sx={{ color, fontWeight: 600, ...props.sx }}>
      {showAbs && formatPrice(pnl)}
      {pnlPct != null && ` (${formatPct(pnlPct)})`}
      {!showAbs && pnlPct != null && formatPct(pnlPct)}
    </Typography>
  );
});
