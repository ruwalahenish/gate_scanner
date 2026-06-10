"use client";
import { Card, CardContent, Typography, Box, type SxProps } from "@mui/material";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import { memo, type ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  color?: string;
  sx?: SxProps;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  onClick?: () => void;
}

export const StatCard = memo(function StatCard({
  label, value, subtitle, icon, color, sx,
  trend, trendValue, onClick,
}: StatCardProps) {
  const trendColor =
    trend === "up"   ? "success.main" :
    trend === "down" ? "error.main"   : "text.disabled";

  return (
    <Card
      onClick={onClick}
      sx={{
        height: "100%",
        cursor: onClick ? "pointer" : "default",
        transition: "transform 200ms ease, border-color 200ms ease, box-shadow 200ms ease",
        ...(onClick && {
          "&:hover": {
            transform: "translateY(-1px)",
            borderColor: "rgba(255,255,255,0.14)",
          },
        }),
        ...sx,
      }}
    >
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start">
          <Box flex={1} minWidth={0}>
            <Typography variant="caption" color="text.secondary" gutterBottom display="block">
              {label}
            </Typography>
            <Typography
              variant="h5"
              fontWeight={700}
              sx={{ color: color ?? "text.primary", fontVariantNumeric: "tabular-nums" }}
            >
              {value}
            </Typography>
            {subtitle && (
              <Typography variant="caption" color="text.secondary">
                {subtitle}
              </Typography>
            )}
            {trendValue && trend && trend !== "neutral" && (
              <Typography variant="caption" sx={{ color: trendColor, display: "block", mt: 0.25 }}>
                {trendValue}
              </Typography>
            )}
          </Box>
          <Box sx={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 0.5 }}>
            {icon && (
              <Box sx={{ color: color ?? "text.secondary", opacity: 0.8 }}>
                {icon}
              </Box>
            )}
            {trend && trend !== "neutral" && (
              <Box sx={{ color: trendColor, lineHeight: 0 }}>
                {trend === "up"
                  ? <TrendingUpIcon sx={{ fontSize: 16 }} />
                  : <TrendingDownIcon sx={{ fontSize: 16 }} />}
              </Box>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
});
