"use client";
import { useState } from "react";
import {
  DataGrid, type GridColDef, type GridRowParams,
} from "@mui/x-data-grid";
import {
  Box, Chip, Typography, Tooltip, IconButton, Collapse,
  Paper, Grid, Button, Divider,
} from "@mui/material";
import { ExpandMore, ExpandLess, ShoppingCart, CheckCircle, Cancel } from "@mui/icons-material";
import { useDispatch } from "react-redux";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { GATEBar } from "@/components/ui/GATEBar";
import { formatPrice, formatPct, formatRR, formatScore } from "@/lib/formatters";
import { openBuyModal } from "@/store/slices/uiSlice";
import type { Signal } from "@/types/signal";

interface SignalTableProps {
  rows: Signal[];
  total: number;
  loading: boolean;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

function BoolIcon({ val }: { val: boolean | null }) {
  if (val === null) return <Typography color="text.disabled">—</Typography>;
  return val
    ? <CheckCircle sx={{ fontSize: 14, color: "success.main" }} />
    : <Cancel sx={{ fontSize: 14, color: "error.main" }} />;
}

function ExpandedDetail({ signal }: { signal: Signal }) {
  const dispatch = useDispatch();
  return (
    <Paper
      elevation={0}
      sx={{ p: 2, bgcolor: "rgba(99,102,241,0.04)", borderTop: "1px solid rgba(255,255,255,0.06)" }}
    >
      <Grid container spacing={2}>
        <Grid item xs={12} md={5}>
          <Typography variant="caption" color="text.secondary" display="block" mb={1}>
            Signal Levels
          </Typography>
          {[
            ["Entry", signal.entry, "primary.main"],
            ["Stop Loss", signal.stop_loss, "error.main"],
            ["T1", signal.t1, "success.light"],
            ["T2", signal.t2, "success.main"],
            ["T3", signal.t3, "success.dark"],
          ].map(([label, val, color]) => (
            <Box key={String(label)} display="flex" justifyContent="space-between" mb={0.5}>
              <Typography variant="caption" color="text.secondary">{label}</Typography>
              <Typography variant="caption" sx={{ color: color as string, fontWeight: 600 }}>
                {formatPrice(val as number | null)}
              </Typography>
            </Box>
          ))}
        </Grid>

        <Grid item xs={12} md={4}>
          <Typography variant="caption" color="text.secondary" display="block" mb={1}>
            Analysis Flags
          </Typography>
          {[
            ["HTF Confirmed", signal.htf_confirmed],
            ["Correction Valid", signal.correction_validated],
            ["Bounce Sequence", signal.bounce_sequence_valid],
            ["Fib Confluence", signal.fib_confluence],
          ].map(([label, val]) => (
            <Box key={String(label)} display="flex" alignItems="center" gap={1} mb={0.5}>
              <BoolIcon val={val as boolean | null} />
              <Typography variant="caption" color="text.secondary">{label}</Typography>
            </Box>
          ))}
        </Grid>

        <Grid item xs={12} md={3}>
          <Typography variant="caption" color="text.secondary" display="block" mb={1}>
            Scores
          </Typography>
          {[
            ["GATE", signal.gate_strength],
            ["Confidence", signal.confidence],
            ["Structure", signal.structure_quality],
            ["Breakout Prob", signal.breakout_probability],
          ].map(([label, val]) => (
            <Box key={String(label)} display="flex" justifyContent="space-between" mb={0.5}>
              <Typography variant="caption" color="text.secondary">{label}</Typography>
              <Typography variant="caption" fontWeight={600}>{formatScore(val as number | null)}</Typography>
            </Box>
          ))}
        </Grid>

        {signal.reasoning && (
          <Grid item xs={12}>
            <Divider sx={{ borderColor: "rgba(255,255,255,0.06)", mb: 1 }} />
            <Typography variant="caption" color="text.secondary">
              {signal.reasoning}
            </Typography>
          </Grid>
        )}

        <Grid item xs={12} sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
          <Button
            size="small"
            variant="contained"
            startIcon={<ShoppingCart />}
            onClick={() => dispatch(openBuyModal(signal.symbol))}
          >
            Paper Buy
          </Button>
        </Grid>
      </Grid>
    </Paper>
  );
}

export function SignalTable({
  rows, total, loading, page, pageSize, onPageChange,
}: SignalTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const columns: GridColDef[] = [
    {
      field: "expand",
      headerName: "",
      width: 40,
      sortable: false,
      renderCell: (params) => (
        <IconButton
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            setExpandedId(expandedId === params.row.id ? null : params.row.id);
          }}
        >
          {expandedId === params.row.id ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
        </IconButton>
      ),
    },
    {
      field: "symbol",
      headerName: "Symbol",
      width: 120,
      renderCell: (p) => (
        <Box>
          <Typography variant="body2" fontWeight={700} color="primary.light" lineHeight={1.2}>
            {p.value}
          </Typography>
          {p.row.company_name && (
            <Typography
              variant="caption"
              color="text.secondary"
              noWrap
              sx={{ display: "block", maxWidth: 110, fontSize: "0.65rem" }}
            >
              {p.row.company_name}
            </Typography>
          )}
        </Box>
      ),
    },
    {
      field: "category",
      headerName: "Category",
      width: 110,
      renderCell: (p) => <CategoryChip category={p.value} />,
    },
    {
      field: "rank_score",
      headerName: "Rank",
      width: 80,
      type: "number",
      renderCell: (p) => (
        <Typography variant="body2" fontWeight={600}>
          {formatScore(p.value)}
        </Typography>
      ),
    },
    {
      field: "gate_strength",
      headerName: "GATE",
      width: 130,
      renderCell: (p) => <GATEBar score={p.value} />,
    },
    {
      field: "signal_timeframe",
      headerName: "TF",
      width: 65,
      renderCell: (p) => (
        <Chip label={p.value ?? "—"} size="small" sx={{ fontSize: "0.68rem", height: 18 }} />
      ),
    },
    {
      field: "entry",
      headerName: "Entry",
      width: 90,
      renderCell: (p) => <Typography variant="body2">{formatPrice(p.value)}</Typography>,
    },
    {
      field: "stop_loss",
      headerName: "SL",
      width: 90,
      renderCell: (p) => (
        <Typography variant="body2" color="error.light">{formatPrice(p.value)}</Typography>
      ),
    },
    {
      field: "t1",
      headerName: "T1",
      width: 90,
      renderCell: (p) => (
        <Typography variant="body2" color="success.light">{formatPrice(p.value)}</Typography>
      ),
    },
    {
      field: "rr_t1",
      headerName: "RR",
      width: 60,
      renderCell: (p) => (
        <Typography variant="body2" fontWeight={600} color={p.value >= 2 ? "success.main" : "text.primary"}>
          {formatRR(p.value)}
        </Typography>
      ),
    },
    {
      field: "confidence",
      headerName: "Conf%",
      width: 70,
      type: "number",
      renderCell: (p) => <Typography variant="body2">{formatScore(p.value)}</Typography>,
    },
    {
      field: "mtf_alignment_pct",
      headerName: "MTF%",
      width: 70,
      type: "number",
      renderCell: (p) => <Typography variant="body2">{formatScore(p.value)}</Typography>,
    },
    {
      field: "side",
      headerName: "Side",
      width: 60,
      renderCell: (p) => (
        <Chip
          label={p.value ?? "—"}
          size="small"
          sx={{
            height: 18, fontSize: "0.68rem",
            bgcolor: p.value === "BUY" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
            color: p.value === "BUY" ? "success.main" : "error.main",
          }}
        />
      ),
    },
  ];

  return (
    <Box>
      <DataGrid
        rows={rows}
        columns={columns}
        loading={loading}
        rowCount={total}
        paginationMode="server"
        paginationModel={{ page, pageSize }}
        onPaginationModelChange={(m) => onPageChange(m.page)}
        pageSizeOptions={[25, 50, 100]}
        disableRowSelectionOnClick
        getRowId={(r) => r.id}
        density="compact"
        sx={{ border: "none", minHeight: 400 }}
        getRowHeight={() => "auto"}
      />

      {/* Expanded row detail */}
      {rows.map((row) => (
        <Collapse key={row.id} in={expandedId === row.id} unmountOnExit>
          <ExpandedDetail signal={row} />
        </Collapse>
      ))}
    </Box>
  );
}
