"use client";
import { Box, Typography, Button, type SxProps } from "@mui/material";
import { memo, type ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  secondaryAction?: { label: string; onClick: () => void };
  sx?: SxProps;
}

export const EmptyState = memo(function EmptyState({
  icon, title, description, action, secondaryAction, sx,
}: EmptyStateProps) {
  return (
    <Box
      role="status"
      aria-label={title}
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      textAlign="center"
      py={5}
      px={3}
      sx={sx}
    >
      {icon && (
        <Box
          sx={{
            width: 64,
            height: 64,
            borderRadius: "50%",
            bgcolor: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.07)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            mb: 2,
            "& svg": { fontSize: 28, color: "text.disabled" },
          }}
        >
          {icon}
        </Box>
      )}
      <Typography variant="body2" fontWeight={600} color="text.secondary" gutterBottom>
        {title}
      </Typography>
      {description && (
        <Typography
          variant="caption"
          color="text.disabled"
          display="block"
          mb={(action || secondaryAction) ? 2 : 0}
        >
          {description}
        </Typography>
      )}
      {(action || secondaryAction) && (
        <Box display="flex" gap={1} flexWrap="wrap" justifyContent="center">
          {action && (
            <Button size="small" variant="outlined" onClick={action.onClick}>
              {action.label}
            </Button>
          )}
          {secondaryAction && (
            <Button size="small" variant="text" color="inherit" onClick={secondaryAction.onClick}
              sx={{ color: "text.secondary" }}>
              {secondaryAction.label}
            </Button>
          )}
        </Box>
      )}
    </Box>
  );
});
