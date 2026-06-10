"use client";
import { Box, LinearProgress, Typography, Tooltip } from "@mui/material";
import { GATE_THRESHOLDS, GATE_COLOR } from "@/lib/constants";
import { memo } from "react";

interface GATEBarProps {
  score: number | null;
  showLabel?: boolean;
}

function getColor(score: number): string {
  if (score >= GATE_THRESHOLDS.HIGH) return GATE_COLOR.HIGH;
  if (score >= GATE_THRESHOLDS.MID)  return GATE_COLOR.MID;
  if (score >= GATE_THRESHOLDS.LOW)  return GATE_COLOR.LOW;
  return GATE_COLOR.FAIL;
}

export const GATEBar = memo(function GATEBar({ score, showLabel = true }: GATEBarProps) {
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
            "& .MuiLinearProgress-bar": {
              bgcolor: color,
              borderRadius: 3,
              transition: "transform 400ms ease",
            },
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
});
