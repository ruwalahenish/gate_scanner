"use client";
import { Box, LinearProgress, Typography, Tooltip } from "@mui/material";

interface GATEBarProps {
  score: number | null;
  showLabel?: boolean;
}

function getColor(score: number): string {
  if (score >= 70) return "#22c55e";
  if (score >= 55) return "#6366f1";
  if (score >= 40) return "#f59e0b";
  return "#ef4444";
}

export function GATEBar({ score, showLabel = true }: GATEBarProps) {
  if (score == null) return <Typography variant="caption" color="text.disabled">—</Typography>;
  const color = getColor(score);
  return (
    <Tooltip title={`GATE Score: ${score.toFixed(0)}/100`} placement="top">
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.8, width: "100%" }}>
        <LinearProgress
          variant="determinate"
          value={score}
          sx={{
            flex: 1,
            height: 5,
            borderRadius: 3,
            bgcolor: "rgba(255,255,255,0.06)",
            "& .MuiLinearProgress-bar": { bgcolor: color, borderRadius: 3 },
          }}
        />
        {showLabel && (
          <Typography variant="caption" sx={{ color, fontWeight: 600, minWidth: 22 }}>
            {score.toFixed(0)}
          </Typography>
        )}
      </Box>
    </Tooltip>
  );
}
