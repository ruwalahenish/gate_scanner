"use client";
import { Card, CardContent, Skeleton, Box, type SxProps } from "@mui/material";

interface SkeletonCardProps {
  rows?: number;
  height?: number;
  sx?: SxProps;
}

/** Shimmer placeholder — use while RTK Query is loading. */
export function SkeletonCard({ rows = 3, height, sx }: SkeletonCardProps) {
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
}

/** Shimmer for a single stat number */
export function SkeletonStat({ sx }: { sx?: SxProps }) {
  return (
    <Box sx={sx}>
      <Skeleton variant="text" width={60} height={14} />
      <Skeleton variant="text" width={40} height={36} />
    </Box>
  );
}
