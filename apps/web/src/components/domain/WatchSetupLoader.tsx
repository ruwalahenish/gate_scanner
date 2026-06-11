"use client";
import { useState } from "react";
import { useGetStockAnalysisQuery } from "@/store/api/stockMasterApi";
import { TradeSetupPanel } from "@/components/domain/TradeSetupPanel";
import { fromLiveAnalysis, type TradeSetup } from "@/lib/tradeSetup";
import type { SignalCategory } from "@/types/signal";
import type { Bar } from "@/types/stock";

interface WatchSetupLoaderProps {
  symbol: string;
  category?: SignalCategory | null;
  /** Partial setup shown (with a "Load trade setup" CTA) before analysis runs. */
  initialSetup: TradeSetup;
  variant?: "full" | "compact";
  showChart?: boolean;
  chartBars?: Bar[];
  chartLoading?: boolean;
  headerTitle?: string;
}

/**
 * Lazily computes a provisional trade setup for a WATCH stock via the live
 * analysis engine. The query is skipped until the user clicks "Load trade
 * setup", so expanding many rows never fires a burst of ~5s calls. The 5-minute
 * RTK cache (keepUnusedDataFor: 300) dedupes repeat opens of the same symbol.
 */
export function WatchSetupLoader({
  symbol,
  category,
  initialSetup,
  variant = "full",
  showChart = false,
  chartBars,
  chartLoading,
  headerTitle = "Trade Setup",
}: WatchSetupLoaderProps) {
  const [triggered, setTriggered] = useState(false);

  const { data, isFetching, isError, refetch } = useGetStockAnalysisQuery(symbol, {
    skip: !triggered,
  });

  if (!triggered) {
    return (
      <TradeSetupPanel
        setup={initialSetup}
        variant={variant}
        headerTitle={headerTitle}
        onLoadSetup={() => setTriggered(true)}
      />
    );
  }

  const setup = data
    ? fromLiveAnalysis(symbol, data, { category: category ?? "WATCH", provenance: "anticipated" })
    : null;

  return (
    <TradeSetupPanel
      setup={setup}
      variant={variant}
      showChart={showChart}
      chartBars={chartBars}
      chartLoading={chartLoading}
      loading={isFetching}
      error={isError ? "Live analysis failed — the data feed may be unavailable." : null}
      onRetry={() => refetch()}
      headerTitle={headerTitle}
    />
  );
}
