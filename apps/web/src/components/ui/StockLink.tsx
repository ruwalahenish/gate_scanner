"use client";
import { memo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Typography, type TypographyProps } from "@mui/material";

interface StockLinkProps extends Omit<TypographyProps, "onClick" | "children"> {
  symbol: string;
}

/**
 * Renders a stock symbol that navigates to its detail page (`/stocks/{symbol}`)
 * on click. Stops event propagation so it can live inside clickable rows
 * (e.g. expandable signal rows) without triggering the row handler.
 *
 * Accepts any Typography prop for styling so it can drop in wherever a raw
 * `<Typography>{symbol}</Typography>` was previously used.
 */
export const StockLink = memo(function StockLink({ symbol, sx, ...rest }: StockLinkProps) {
  const router = useRouter();

  const navigate = useCallback(() => {
    router.push(`/stocks/${encodeURIComponent(symbol)}`);
  }, [router, symbol]);

  return (
    <Typography
      role="link"
      tabIndex={0}
      aria-label={`View ${symbol} details`}
      onClick={(e) => {
        e.stopPropagation();
        navigate();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          navigate();
        }
      }}
      sx={{
        cursor: "pointer",
        width: "fit-content",
        "&:hover": { textDecoration: "underline" },
        "&:focus-visible": {
          outline: "2px solid rgba(99,102,241,0.5)",
          outlineOffset: 2,
          borderRadius: 1,
        },
        ...sx,
      }}
      {...rest}
    >
      {symbol}
    </Typography>
  );
});
