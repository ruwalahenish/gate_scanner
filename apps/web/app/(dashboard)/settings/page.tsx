"use client";
import {
  Box, Typography, Card, CardContent, TextField, Button,
  Divider, Grid, Alert,
} from "@mui/material";
import { useState } from "react";
import { API_URL, WS_URL } from "@/lib/constants";

export default function SettingsPage() {
  const [saved, setSaved] = useState(false);

  return (
    <Box>
      <Typography variant="h6" fontWeight={700} mb={2}>Settings</Typography>

      <Grid container spacing={3}>
        {/* Connection settings */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>Connection</Typography>
              <Box display="flex" flexDirection="column" gap={2} mt={1}>
                <TextField
                  label="API URL"
                  value={API_URL}
                  disabled
                  fullWidth
                  helperText="Set via NEXT_PUBLIC_API_URL env variable"
                />
                <TextField
                  label="WebSocket URL"
                  value={WS_URL}
                  disabled
                  fullWidth
                  helperText="Set via NEXT_PUBLIC_WS_URL env variable"
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Portfolio settings */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>Portfolio</Typography>
              <Alert severity="info" sx={{ mt: 1 }}>
                Initial capital is set in NeonDB{" "}
                <code>portfolio_config</code> table.
                To change it, run:
                <br />
                <code>UPDATE portfolio_config SET initial_capital=2000000, current_capital=2000000;</code>
              </Alert>
            </CardContent>
          </Card>
        </Grid>

        {/* GATE Config reference */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>GATE Engine Configuration</Typography>
              <Typography variant="body2" color="text.secondary" mb={1}>
                All thresholds are in{" "}
                <code>gate_scanner/config.py</code>.
                Restart the backend after changes.
              </Typography>
              <Box sx={{
                bgcolor: "rgba(0,0,0,0.3)",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: 1,
                p: 2,
                fontFamily: "monospace",
                fontSize: "0.78rem",
                color: "text.secondary",
              }}>
                {[
                  "GATE_WEIGHTS = { bb_squeeze: 0.22, atr_contraction: 0.18, ... }",
                  "RANK_WEIGHTS = { gate_strength: 0.30, mtf_alignment: 0.25, ... }",
                  "MIN_RR_RATIO = 1.5",
                  "MIN_AVG_VOLUME = 100_000",
                  "MAX_SL_DISTANCE_PCT = 0.12",
                ].map((line) => (
                  <div key={line}>{line}</div>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
