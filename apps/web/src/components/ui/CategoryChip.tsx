"use client";
import { Chip, type ChipProps } from "@mui/material";
import { CATEGORY_COLORS } from "@/lib/constants";
import type { SignalCategory } from "@/types/signal";

interface CategoryChipProps extends Omit<ChipProps, "color"> {
  category: SignalCategory;
}

export function CategoryChip({ category, ...props }: CategoryChipProps) {
  const color = CATEGORY_COLORS[category] ?? "#64748b";
  return (
    <Chip
      label={category}
      size="small"
      {...props}
      sx={{
        backgroundColor: `${color}20`,
        color: color,
        borderColor: `${color}40`,
        border: "1px solid",
        fontWeight: 600,
        fontSize: "0.68rem",
        height: 20,
        ...props.sx,
      }}
    />
  );
}
