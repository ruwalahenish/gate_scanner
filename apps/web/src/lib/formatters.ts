/** Format a price in INR with commas */
export function formatPrice(val: number | null | undefined, decimals = 2): string {
  if (val == null) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(val);
}

/** Format a percentage with sign */
export function formatPct(val: number | null | undefined, decimals = 1): string {
  if (val == null) return "—";
  const sign = val > 0 ? "+" : "";
  return `${sign}${val.toFixed(decimals)}%`;
}

/** Format a risk-reward ratio */
export function formatRR(val: number | null | undefined): string {
  if (val == null) return "—";
  return `${val.toFixed(1)}x`;
}

/** Format a score out of 100 */
export function formatScore(val: number | null | undefined): string {
  if (val == null) return "—";
  return val.toFixed(0);
}

/** Format large numbers with K/L/Cr suffix */
export function formatCompact(val: number | null | undefined): string {
  if (val == null) return "—";
  if (val >= 1_00_00_000) return `₹${(val / 1_00_00_000).toFixed(2)} Cr`;
  if (val >= 1_00_000)    return `₹${(val / 1_00_000).toFixed(2)} L`;
  if (val >= 1_000)       return `₹${(val / 1_000).toFixed(1)} K`;
  return formatPrice(val);
}

/** Format IST datetime */
export function formatIST(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(isoString));
}

/** Check if currently IST market hours (9:15–15:30, Mon–Fri) */
export function isMarketHours(): boolean {
  const now = new Date();
  const ist = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
  const day = ist.getDay();
  if (day === 0 || day === 6) return false;
  const t = ist.getHours() * 60 + ist.getMinutes();
  return t >= 555 && t <= 930;
}
