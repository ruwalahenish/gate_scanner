"use client";
import { Box, Typography, Button, type SxProps } from "@mui/material";
import { ErrorOutline, Refresh } from "@mui/icons-material";

interface PageErrorProps {
  message?: string;
  detail?: string;
  onRetry?: () => void;
  sx?: SxProps;
}

/** Drop-in replacement for any RTK Query `isError` state. */
export function PageError({ message, detail, onRetry, sx }: PageErrorProps) {
  return (
    <Box
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      textAlign="center"
      py={6}
      px={3}
      sx={sx}
    >
      <ErrorOutline sx={{ fontSize: 38, color: "error.main", mb: 1.5, opacity: 0.8 }} />
      <Typography variant="body2" fontWeight={600} color="text.secondary" gutterBottom>
        {message ?? "Something went wrong"}
      </Typography>
      {detail && (
        <Typography variant="caption" color="text.disabled" display="block" mb={2}>
          {detail}
        </Typography>
      )}
      {onRetry && (
        <Button
          size="small"
          variant="outlined"
          startIcon={<Refresh />}
          onClick={onRetry}
          sx={{ mt: 1 }}
        >
          Retry
        </Button>
      )}
    </Box>
  );
}
