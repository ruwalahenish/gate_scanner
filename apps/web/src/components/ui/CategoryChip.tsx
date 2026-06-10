"use client";
import { Chip, type ChipProps } from "@mui/material";
import { CATEGORY_COLORS } from "@/lib/constants";
import type { SignalCategory } from "@/types/signal";
import { memo } from "react";

type ChipSize = "xs" | "sm" | "md";

interface CategoryChipProps extends Omit<ChipProps, "color" | "size"> {
  category: SignalCategory;
  chipSize?: ChipSize;
}

const HEIGHT:    Record<ChipSize, number> = { xs: 18, sm: 20, md: 24 };
const FONT_SIZE: Record<ChipSize, string> = { xs: "0.62rem", sm: "0.68rem", md: "0.75rem" };

function buildChipSx(color: string, chipSize: ChipSize, extraSx?: ChipProps["sx"]) {
  return {
    backgroundColor: `${color}20`,
    color,
    borderColor: `${color}40`,
    border: "1px solid",
    fontWeight: 600,
    fontSize: FONT_SIZE[chipSize],
    height: HEIGHT[chipSize],
    ...extraSx,
  };
}

export const CategoryChip = memo(function CategoryChip({
  category, chipSize = "sm", ...props
}: CategoryChipProps) {
  const color = CATEGORY_COLORS[category] ?? "#64748b";
  return (
    <Chip
      label={category}
      {...props}
      sx={buildChipSx(color, chipSize, props.sx)}
    />
  );
});
