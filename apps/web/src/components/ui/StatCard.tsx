"use client";
import { Card, CardContent, Typography, Box, type SxProps } from "@mui/material";
import { type ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  color?: string;
  sx?: SxProps;
}

export function StatCard({ label, value, subtitle, icon, color, sx }: StatCardProps) {
  return (
    <Card sx={{ height: "100%", ...sx }}>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start">
          <Box>
            <Typography variant="caption" color="text.secondary" gutterBottom>
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
          </Box>
          {icon && (
            <Box sx={{ color: color ?? "text.secondary", opacity: 0.8 }}>
              {icon}
            </Box>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}
