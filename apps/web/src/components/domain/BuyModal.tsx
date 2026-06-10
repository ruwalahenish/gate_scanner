"use client";
import { useState, useCallback } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Button, Typography, Box, Divider, Alert, CircularProgress,
} from "@mui/material";
import { useSelector, useDispatch } from "react-redux";
import { enqueueSnackbar } from "notistack";
import { useBuyMutation } from "@/store/api/portfolioApi";
import { closeBuyModal } from "@/store/slices/uiSlice";
import { selectBuyModalOpen, selectBuyModalSymbol } from "@/store/selectors";
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
  const dispatch       = useDispatch();
  const buyModalOpen   = useSelector(selectBuyModalOpen);
  const buyModalSymbol = useSelector(selectBuyModalSymbol);
  const [buy, { isLoading }] = useBuyMutation();

  const [qty,   setQty]   = useState("10");
  const [price, setPrice] = useState(prefillSignal?.entry?.toFixed(2) ?? "");
  const [sl,    setSl]    = useState(prefillSignal?.stop_loss?.toFixed(2) ?? "");
  const [t1,    setT1]    = useState(prefillSignal?.t1?.toFixed(2) ?? "");
  const [error,       setError]       = useState("");
  const [submitted,   setSubmitted]   = useState(false);

  const qtyNum   = parseFloat(qty);
  const priceNum = parseFloat(price);
  const slNum    = parseFloat(sl);
  const t1Num    = parseFloat(t1);

  const qtyValid   = !isNaN(qtyNum)   && qtyNum > 0;
  const priceValid = !isNaN(priceNum) && priceNum > 0;
  const cost = qtyNum * priceNum;
  const isValid = qtyValid && priceValid;

  const potentialT1 = (t1 && sl && isValid)
    ? (t1Num - priceNum) * qtyNum
    : null;
  const maxRisk = (sl && isValid)
    ? (priceNum - slNum) * qtyNum
    : null;

  const handleClose = useCallback(() => {
    dispatch(closeBuyModal());
    setError("");
    setSubmitted(false);
  }, [dispatch]);

  const handleSubmit = useCallback(async () => {
    setSubmitted(true);
    if (!isValid || !buyModalSymbol) return;
    setError("");
    try {
      const result = await buy({
        symbol:    buyModalSymbol,
        quantity:  parseInt(qty),
        price:     priceNum,
        signal_id: prefillSignal?.id,
        stop_loss: sl ? slNum : undefined,
        t1:        t1 ? t1Num : undefined,
      }).unwrap();
      enqueueSnackbar(
        `Bought ${qty} ${buyModalSymbol} @ ₹${price} (Cost: ${formatPrice(result.cost)})`,
        { variant: "success" }
      );
      handleClose();
    } catch (err: unknown) {
      const msg = (err as { data?: { detail?: string } })?.data?.detail ?? "Buy failed";
      setError(msg);
    }
  }, [buy, buyModalSymbol, handleClose, isValid, price, priceNum, prefillSignal?.id, qty, sl, slNum, t1, t1Num]);

  return (
    <Dialog
      open={buyModalOpen}
      onClose={handleClose}
      maxWidth="xs"
      fullWidth
      aria-label="Paper buy order"
      aria-labelledby="buy-modal-title"
    >
      <DialogTitle id="buy-modal-title">
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
            error={submitted && !qtyValid}
            helperText={submitted && !qtyValid ? "Enter a valid quantity" : undefined}
            fullWidth
          />
          <TextField
            label="Price (₹)"
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            error={submitted && !priceValid}
            helperText={submitted && !priceValid ? "Enter a valid price" : undefined}
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
              <Box display="flex" flexDirection="column" gap={0.5}>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Total Cost</Typography>
                  <Typography variant="body2" fontWeight={700}>{formatPrice(cost)}</Typography>
                </Box>
                {potentialT1 !== null && (
                  <Box display="flex" justifyContent="space-between">
                    <Typography variant="caption" color="text.disabled">Potential at T1</Typography>
                    <Typography variant="caption" sx={{ color: potentialT1 >= 0 ? "success.light" : "error.light" }}>
                      {potentialT1 >= 0 ? "+" : ""}{formatPrice(potentialT1)}
                    </Typography>
                  </Box>
                )}
                {maxRisk !== null && (
                  <Box display="flex" justifyContent="space-between">
                    <Typography variant="caption" color="text.disabled">Max Risk</Typography>
                    <Typography variant="caption" color="error.light">
                      {formatPrice(maxRisk)}
                    </Typography>
                  </Box>
                )}
              </Box>
            </>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} aria-label="Cancel buy order">Cancel</Button>
        <Button
          variant="contained"
          color="success"
          onClick={handleSubmit}
          disabled={isLoading}
          startIcon={isLoading ? <CircularProgress size={14} color="inherit" /> : undefined}
        >
          {isLoading ? "Buying…" : "Confirm Buy"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
