"use client";
import { Typography, type TypographyProps } from "@mui/material";
import { formatPct, formatPrice } from "@/lib/formatters";

interface PnlBadgeProps extends Omit<TypographyProps, "color"> {
  pnl: number | null | undefined;
  pnlPct?: number | null;
  showAbs?: boolean;
}

export function PnlBadge({ pnl, pnlPct, showAbs = true, ...props }: PnlBadgeProps) {
  if (pnl == null) return <Typography {...props} color="text.disabled">—</Typography>;
  const isPositive = pnl >= 0;
  const color = isPositive ? "success.main" : "error.main";
  return (
    <Typography {...props} sx={{ color, fontWeight: 600, ...props.sx }}>
      {showAbs && formatPrice(pnl)}
      {pnlPct != null && ` (${formatPct(pnlPct)})`}
      {!showAbs && pnlPct != null && formatPct(pnlPct)}
    </Typography>
  );
}
