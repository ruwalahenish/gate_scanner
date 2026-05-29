"use client";
import { useState } from "react";
import { Box, Typography, Alert } from "@mui/material";
import { SignalTable } from "@/components/domain/SignalTable";
import { SignalFilterBar } from "@/components/domain/SignalFilterBar";
import { useGetSignalsQuery } from "@/store/api/signalsApi";
import type { SignalFilters } from "@/types/signal";

export default function SignalsPage() {
  const [page, setPage] = useState(0);
  const [filters, setFilters] = useState<SignalFilters>({ limit: 50, offset: 0 });

  const { data, isLoading, isError } = useGetSignalsQuery({
    ...filters,
    limit: 50,
    offset: page * 50,
  });

  const handleFilterChange = (partial: Partial<SignalFilters>) => {
    setFilters((prev) => ({ ...prev, ...partial }));
    setPage(0);
  };

  return (
    <Box>
      <Typography variant="h6" fontWeight={700} mb={2}>
        Live Signals
        {data && (
          <Typography component="span" variant="body2" color="text.secondary" ml={1}>
            ({data.total} signals)
          </Typography>
        )}
      </Typography>

      <SignalFilterBar filters={filters} onChange={handleFilterChange} />

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load signals. Make sure the backend is running.
        </Alert>
      )}

      <SignalTable
        rows={data?.items ?? []}
        total={data?.total ?? 0}
        loading={isLoading}
        page={page}
        pageSize={50}
        onPageChange={setPage}
      />
    </Box>
  );
}
