"use client";
import { useState } from "react";
import {
  Box, Typography, Card, CardContent, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Chip, Button, Dialog,
  DialogTitle, DialogContent, DialogActions, TextField, Select,
  MenuItem, FormControl, InputLabel, Alert as MuiAlert, IconButton,
} from "@mui/material";
import { Add, Delete, CheckCircle } from "@mui/icons-material";
import { enqueueSnackbar } from "notistack";
import {
  useGetAlertsQuery,
  useCreateAlertMutation,
  useDismissAlertMutation,
  useDeleteAlertMutation,
} from "@/store/api/alertsApi";
import { useDispatch } from "react-redux";
import { alertsRead } from "@/store/slices/wsSlice";
import { formatPrice, formatIST } from "@/lib/formatters";
import type { AlertType } from "@/types/alert";

const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  price_above:       "Price Above",
  price_below:       "Price Below",
  gate_score_gte:    "GATE Score ≥",
  gate_score_lte:    "GATE Score ≤",
  volume_spike:      "Volume Spike",
  category_upgrade:  "Category Upgrade",
  breakout_detected: "Breakout Detected",
  sl_breach_warning: "SL Breach Warning",
  target_proximity:  "Target Proximity",
};

function CreateAlertDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [createAlert, { isLoading }] = useCreateAlertMutation();
  const [symbol, setSymbol] = useState("");
  const [type, setType] = useState<AlertType>("price_above");
  const [threshold, setThreshold] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleCreate = async () => {
    setError("");
    if (!symbol) { setError("Symbol required"); return; }
    try {
      await createAlert({
        symbol: symbol.toUpperCase(),
        alert_type: type,
        threshold_value: threshold ? parseFloat(threshold) : undefined,
        message: message || undefined,
      }).unwrap();
      enqueueSnackbar("Alert created", { variant: "success" });
      onClose();
    } catch (err: unknown) {
      setError((err as { data?: { detail?: string } })?.data?.detail ?? "Failed to create alert");
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Create Alert</DialogTitle>
      <DialogContent>
        {error && <MuiAlert severity="error" sx={{ mb: 2 }}>{error}</MuiAlert>}
        <Box display="flex" flexDirection="column" gap={2} mt={1}>
          <TextField label="Symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)} fullWidth />
          <FormControl fullWidth>
            <InputLabel>Alert Type</InputLabel>
            <Select value={type} label="Alert Type" onChange={(e) => setType(e.target.value as AlertType)}>
              {Object.entries(ALERT_TYPE_LABELS).map(([k, v]) => (
                <MenuItem key={k} value={k}>{v}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Threshold (₹ or score)"
            type="number"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            fullWidth
          />
          <TextField
            label="Custom Message (optional)"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            fullWidth
            multiline
            rows={2}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={handleCreate} disabled={isLoading}>
          {isLoading ? "Creating…" : "Create"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function AlertsPage() {
  const dispatch = useDispatch();
  const [createOpen, setCreateOpen] = useState(false);
  const [filter, setFilter] = useState<string>("");
  const { data: alerts } = useGetAlertsQuery(filter ? { status: filter } : undefined);
  const [dismiss] = useDismissAlertMutation();
  const [deleteAlert] = useDeleteAlertMutation();

  const handleOpen = () => {
    dispatch(alertsRead());
    setCreateOpen(true);
  };

  return (
    <Box>
      <CreateAlertDialog open={createOpen} onClose={() => setCreateOpen(false)} />

      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6" fontWeight={700}>Alerts</Typography>
        <Button variant="contained" size="small" startIcon={<Add />} onClick={handleOpen}>
          New Alert
        </Button>
      </Box>

      {/* Status filter */}
      <Box display="flex" gap={1} mb={2}>
        {["", "active", "triggered", "dismissed"].map((s) => (
          <Chip
            key={s || "all"}
            label={s || "All"}
            size="small"
            onClick={() => setFilter(s)}
            variant={filter === s ? "filled" : "outlined"}
            color={filter === s ? "primary" : "default"}
            sx={{ cursor: "pointer" }}
          />
        ))}
      </Box>

      <Card>
        <CardContent sx={{ p: 0 }}>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  {["Symbol", "Type", "Threshold", "Status", "Triggered At", "Price", "Actions"].map((h) => (
                    <TableCell key={h} sx={{ color: "text.secondary", fontSize: "0.75rem" }}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {((alerts as unknown[] | undefined) ?? []).map((a: unknown) => {
                  const alert = a as {
                    id: string; symbol: string; alert_type: AlertType;
                    status: string; threshold_value?: number;
                    triggered_at?: string; triggered_price?: number;
                  };
                  return (
                    <TableRow key={alert.id} hover>
                      <TableCell fontWeight={600}>{alert.symbol}</TableCell>
                      <TableCell>{ALERT_TYPE_LABELS[alert.alert_type] ?? alert.alert_type}</TableCell>
                      <TableCell>{alert.threshold_value ? formatPrice(alert.threshold_value) : "—"}</TableCell>
                      <TableCell>
                        <Chip
                          label={alert.status}
                          size="small"
                          sx={{
                            height: 18, fontSize: "0.68rem",
                            bgcolor: alert.status === "active" ? "rgba(99,102,241,0.15)"
                              : alert.status === "triggered" ? "rgba(245,158,11,0.15)"
                              : "rgba(100,116,139,0.15)",
                            color: alert.status === "active" ? "primary.main"
                              : alert.status === "triggered" ? "warning.main"
                              : "text.secondary",
                          }}
                        />
                      </TableCell>
                      <TableCell sx={{ fontSize: "0.75rem", color: "text.secondary" }}>
                        {formatIST(alert.triggered_at ?? null)}
                      </TableCell>
                      <TableCell>{formatPrice(alert.triggered_price ?? null)}</TableCell>
                      <TableCell>
                        <Box display="flex" gap={0.5}>
                          {alert.status === "triggered" && (
                            <IconButton
                              size="small"
                              onClick={() => dismiss(alert.id)}
                              title="Dismiss"
                            >
                              <CheckCircle fontSize="small" sx={{ color: "success.main" }} />
                            </IconButton>
                          )}
                          <IconButton
                            size="small"
                            onClick={() => deleteAlert(alert.id)}
                            title="Delete"
                          >
                            <Delete fontSize="small" sx={{ color: "error.main" }} />
                          </IconButton>
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  );
}
