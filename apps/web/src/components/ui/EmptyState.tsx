"use client";
import { Box, Typography, Button, type SxProps } from "@mui/material";
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  sx?: SxProps;
}

export function EmptyState({ icon, title, description, action, sx }: EmptyStateProps) {
  return (
    <Box
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
        <Box sx={{ color: "text.disabled", mb: 1.5, "& svg": { fontSize: 40 } }}>
          {icon}
        </Box>
      )}
      <Typography variant="body2" fontWeight={600} color="text.secondary" gutterBottom>
        {title}
      </Typography>
      {description && (
        <Typography variant="caption" color="text.disabled" display="block" mb={action ? 2 : 0}>
          {description}
        </Typography>
      )}
      {action && (
        <Button size="small" variant="outlined" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </Box>
  );
}
