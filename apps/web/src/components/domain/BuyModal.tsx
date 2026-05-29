"use client";
import { useState } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Button, Typography, Box, Divider, Alert,
} from "@mui/material";
import { useSelector, useDispatch } from "react-redux";
import { enqueueSnackbar } from "notistack";
import { useBuyMutation } from "@/store/api/portfolioApi";
import { closeBuyModal } from "@/store/slices/uiSlice";
import type { RootState } from "@/store";
import { formatPrice } from "@/lib/formatters";

interface BuyModalProps {
  prefillSignal?: {
    entry: number | null;
    stop_loss: number | null;
    t1: number | null;
    t2: number | null;
    t3: number | null;
    id: string;
  } | null;
}

export function BuyModal({ prefillSignal }: BuyModalProps) {
  const dispatch = useDispatch();
  const { buyModalOpen, buyModalSymbol } = useSelector((s: RootState) => s.ui);
  const [buy, { isLoading }] = useBuyMutation();

  const [qty, setQty] = useState("10");
  const [price, setPrice] = useState(
    prefillSignal?.entry?.toFixed(2) ?? ""
  );
  const [sl, setSl] = useState(prefillSignal?.stop_loss?.toFixed(2) ?? "");
  const [t1, setT1] = useState(prefillSignal?.t1?.toFixed(2) ?? "");
  const [error, setError] = useState("");

  const cost = parseFloat(qty) * parseFloat(price);
  const isValid = !isNaN(cost) && cost > 0;

  const handleSubmit = async () => {
    setError("");
    if (!buyModalSymbol) return;
    try {
      const result = await buy({
        symbol: buyModalSymbol,
        quantity: parseInt(qty),
        price: parseFloat(price),
        signal_id: prefillSignal?.id,
        stop_loss: sl ? parseFloat(sl) : undefined,
        t1: t1 ? parseFloat(t1) : undefined,
      }).unwrap();
      enqueueSnackbar(
        `Bought ${qty} ${buyModalSymbol} @ ₹${price} (Cost: ${formatPrice(result.cost)})`,
        { variant: "success" }
      );
      dispatch(closeBuyModal());
    } catch (err: unknown) {
      const msg = (err as { data?: { detail?: string } })?.data?.detail ?? "Buy failed";
      setError(msg);
    }
  };

  return (
    <Dialog open={buyModalOpen} onClose={() => dispatch(closeBuyModal())} maxWidth="xs" fullWidth>
      <DialogTitle>
        Paper Buy — {buyModalSymbol}
      </DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Box display="flex" flexDirection="column" gap={2} mt={1}>
          <TextField
            label="Quantity"
            type="number"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            inputProps={{ min: 1, max: 100000 }}
            fullWidth
          />
          <TextField
            label="Price (₹)"
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            fullWidth
          />
          <TextField
            label="Stop Loss (₹) — optional"
            type="number"
            value={sl}
            onChange={(e) => setSl(e.target.value)}
            fullWidth
          />
          <TextField
            label="Target T1 (₹) — optional"
            type="number"
            value={t1}
            onChange={(e) => setT1(e.target.value)}
            fullWidth
          />

          {isValid && (
            <>
              <Divider />
              <Box display="flex" justifyContent="space-between">
                <Typography variant="body2" color="text.secondary">Total Cost</Typography>
                <Typography variant="body2" fontWeight={700}>{formatPrice(cost)}</Typography>
              </Box>
            </>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => dispatch(closeBuyModal())}>Cancel</Button>
        <Button
          variant="contained"
          color="success"
          onClick={handleSubmit}
          disabled={!isValid || isLoading}
        >
          {isLoading ? "Buying…" : "Confirm Buy"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
