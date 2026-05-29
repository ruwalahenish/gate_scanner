"use client";
import { useState } from "react";
import {
  Box, Typography, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Paper, IconButton, TextField, Button, Alert,
} from "@mui/material";
import { Delete, Add } from "@mui/icons-material";
import { enqueueSnackbar } from "notistack";
import Link from "next/link";
import {
  useGetWatchlistQuery,
  useAddToWatchlistMutation,
  useRemoveFromWatchlistMutation,
} from "@/store/api/marketApi";
import { formatIST } from "@/lib/formatters";

export default function WatchlistPage() {
  const [newSymbol, setNewSymbol] = useState("");
  const { data: watchlist, isLoading } = useGetWatchlistQuery();
  const [addToWatchlist] = useAddToWatchlistMutation();
  const [removeFromWatchlist] = useRemoveFromWatchlistMutation();

  const handleAdd = async () => {
    const sym = newSymbol.trim().toUpperCase();
    if (!sym) return;
    try {
      await addToWatchlist(sym).unwrap();
      enqueueSnackbar(`${sym} added to watchlist`, { variant: "success" });
      setNewSymbol("");
    } catch (err: unknown) {
      const msg = (err as { data?: { detail?: string } })?.data?.detail ?? "Failed";
      enqueueSnackbar(msg, { variant: "error" });
    }
  };

  const handleRemove = async (symbol: string) => {
    await removeFromWatchlist(symbol).unwrap();
    enqueueSnackbar(`${symbol} removed`, { variant: "info" });
  };

  return (
    <Box>
      <Typography variant="h6" fontWeight={700} mb={2}>Watchlist</Typography>

      {/* Add symbol */}
      <Box display="flex" gap={1} mb={3} maxWidth={400}>
        <TextField
          size="small"
          placeholder="e.g. RELIANCE"
          value={newSymbol}
          onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          fullWidth
        />
        <Button variant="contained" startIcon={<Add />} onClick={handleAdd}>
          Add
        </Button>
      </Box>

      <TableContainer component={Paper} elevation={0} sx={{ border: "1px solid rgba(255,255,255,0.06)" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              {["Symbol", "Added At", "Notes", "Action"].map((h) => (
                <TableCell key={h} sx={{ color: "text.secondary", fontSize: "0.75rem" }}>{h}</TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {((watchlist as { id: string; symbol: string; added_at: string; notes?: string }[] | undefined) ?? [])
              .map((item) => (
                <TableRow key={item.id} hover>
                  <TableCell>
                    <Link
                      href={`/signals/${item.symbol}`}
                      style={{ color: "#818cf8", fontWeight: 700, textDecoration: "none" }}
                    >
                      {item.symbol}
                    </Link>
                  </TableCell>
                  <TableCell sx={{ color: "text.secondary", fontSize: "0.75rem" }}>
                    {formatIST(item.added_at)}
                  </TableCell>
                  <TableCell sx={{ color: "text.secondary", fontSize: "0.75rem" }}>
                    {item.notes ?? "—"}
                  </TableCell>
                  <TableCell>
                    <IconButton
                      size="small"
                      onClick={() => handleRemove(item.symbol)}
                      title="Remove from watchlist"
                    >
                      <Delete fontSize="small" sx={{ color: "error.light" }} />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            {!isLoading && (!watchlist || (watchlist as unknown[]).length === 0) && (
              <TableRow>
                <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">
                    Watchlist is empty — add symbols above
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
