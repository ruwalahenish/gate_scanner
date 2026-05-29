# GATE Trading Strategy
### EMA-Based Correction & Cycle Framework

---

## Core Philosophy

> **Do not look for the trend — look for the correction.**

Markets and individual stocks move in a perpetual sequence:

**Trend → Correction → Trend**

Understanding where a correction is in its lifecycle is the single most important skill this strategy develops.

---

## Types of Correction

| Type | Definition |
|---|---|
| **Time Correction** | The moving average (mean) converges toward the actual price. Price holds its level while time passes until the mean catches up. |
| **Price Correction** | The actual price pulls back toward the moving average (mean). |

---

## Market Cycles

- Markets move in a continuous cycle of **expansion** and **contraction**.
- Stock prices alternate between periods of **low volatility** (contraction) and **high volatility** (expansion).
- **Breakouts and breakdowns** occur when prices transition from contraction to expansion.
- **Narrow-range periods** (range contraction) signal an impending range expansion.

> **The cycles are the only truth — everything else is negotiable.**

---

## Market Timeframe Hierarchy (Volatility Family Tree)

| Volatility Level | Timeframes |
|---|---|
| Very High | 1 Min, 3 Min, 5 Min, 10 Min, 15 Min |
| High | 30 Min, 1 Hr, 2 Hr |
| Medium | 3 Hr, 4 Hr, Daily |
| Low | Weekly, Monthly, Yearly |

### Key Principle — Timeframe Cascade

When a price transitions from contraction to expansion (or vice versa), it is **first visible in the smallest timeframe** and then propagates upward:

```
1 Min → 3 Min → 5 Min → 10 Min → 15 Min → 30 Min → 1 Hr → 2 Hr → 3 Hr → 4 Hr → Daily → Weekly → Monthly → Yearly
```

> If the correction completes within a given timeframe, the trend on that timeframe is considered to be continuing.

---

## Mean Reversion & Mean Deviation

### Mean Reversion
*(When the actual price is near the average price)*

A mathematical concept based on the principle that both a stock's high and low prices are temporary. Over time, a stock's price will tend to revert toward its average (mean) price.

### Mean Deviation
*(When the actual price is far from the average price)*

- If the current market price is **below** the average price → the stock is considered attractive for purchase, as the price is expected to rise back toward the mean.
- If the current market price is **above** the average price → the price is expected to fall back toward the mean.

In both cases, deviations from the average price are expected to revert to the mean.

---

## Core Rules

1. The actual price **always** returns to its average price.
2. **(Most Critical Rule)** No new trend will begin until the actual price and the mean (average) price **meet at the same level**. If this convergence has not occurred, any apparent trend is not a genuine trend.
3. If the actual price has not yet touched the mean (average) price, the market is still considered to be **in a trend**.

### How Does a Correction End?

> A correction ends when the price **touches the mean (average) price**.

---

## Setup — Indicators Required

### Exponential Moving Averages (EMAs)

| EMA | Role |
|---|---|
| **20 EMA** | End of the 1st correction bounce |
| **50 EMA** | End of the 2nd correction bounce |
| **100 EMA** | End of the 3rd correction bounce |
| **200 EMA** | End of the final correction; start of the real trend |

### ADX — Trend Strength Confirmation (S-6)

The **Average Directional Index (ADX, period 14)** is used as an optional confirmation layer:

| ADX Value | Interpretation |
|---|---|
| ≤ 15 | Sideways / contracting — ideal GATE formation zone |
| 15–25 | Weak trend — correction likely still in progress |
| 25–40 | Moderate trend — valid trending phase |
| ≥ 40 | Strong trend — high-conviction directional move |

> During a GATE formation, **ADX should be low (≤ 15–20)**. A high ADX during an apparent GATE is a warning sign — the contraction may not be genuine.

---

## EMA Rules & Facts

- **Any correction on any timeframe completes at the 200 EMA.** If the price reverses without touching the 200 EMA, the correction is incomplete — it is a false reversal.
- The **1st bounce** (correction) after a new trend will end at the **20 EMA**.
- The **2nd bounce** ends at the **50 EMA**.
- The **3rd bounce** ends at the **100 EMA**.
- After the price touches the **200 EMA** for the first time, the **real trend begins**.
- If the price touches the 200 EMA on the first attempt, it will **not** immediately continue to the upper or lower side.

### Correction End Conditions

| Correction Type | Condition for Completion |
|---|---|
| **Price Correction** | Price reaches the 200 EMA |
| **Time Correction** | All 4 EMAs (20 / 50 / 100 / 200) converge to the same level |

> When both price correction and time correction are complete, a **new trend will begin**.

### Timeframe Transition via 200 EMA

If the price **breaks through all 4 EMAs** on a given timeframe, it signals readiness to move into the **next higher timeframe**.

**Example:** If the price breaks above the 200 EMA on the 5-minute chart, the price is set to move into the 10-minute timeframe context.

---

## Exception — Monthly Timeframe (Index / Blue-Chip Stocks)

> On the **Monthly timeframe**, major indices and blue-chip stocks will **not** touch the 200 EMA during corrections. The correction will end at the **100 EMA** instead.

---

## Typical Correction Durations

| Timeframe | Correction Duration |
|---|---|
| Weekly | 2 – 2.5 Years |
| Daily | 6 – 12 Months |
| Monthly | 10 – 11 Years |

---

## Chart Settings

> **Always use Logarithmic (Log) Scale on charts.**
> This applies to higher timeframes (Daily and above). For lower timeframes (intraday), log scale is not necessary.

---

## GATE Formation

The GATE is a period of tight, narrow-range price action (contraction) before a major breakout.

- **No major trend ends with a GATE formation.** The trend will resume once the GATE formation tightens.
- **(Fact)** If the previous GATE was in an **uptrend**, there is a **90% probability** that the next GATE will also produce an uptrend.
- Whenever a GATE formation **breaks**, the price will accelerate sharply.
- If the price exits a GATE and **breaks out from the high of the range**, assume it will move into the **next higher timeframe** (100% probability).

### GATE Detection — Quantified Definition (S-1)

A GATE is confirmed when the following **5 contraction signals** are simultaneously active. Each component is scored 0–1; the weighted composite score ranges from 0–100.

| Component | Signal | Weight |
|---|---|---|
| **Bollinger Band Squeeze** | BB width in the bottom 20% of the last 100 bars | 22% |
| **ATR Contraction** | 14-period ATR in the bottom 25% of the last 100 bars | 18% |
| **EMA Compression** | Spread of all 4 EMAs (20/50/100/200) < 4% of price | 22% |
| **Narrow Range Candles** | Average range of last 5 candles < 1× trailing ATR | 13% |
| **Volume Contraction** | 10-bar average volume < 50-bar average volume | 13% |
| **ADX Contraction** | ADX (14) ≤ 15 (weak/sideways trend confirms contraction) | 12% |

> **GATE confirmed when composite score ≥ 55.** Score ≥ 70 = Strong GATE.

---

## Stop Loss

The stop loss is based on the 200 EMA of the **next lower timeframe** relative to the breakout timeframe.

| Breakout Timeframe | Stop Loss |
|---|---|
| Daily | 4-Hour 200 EMA |
| 4-Hour | 2-Hour 200 EMA |
| 1-Hour | 30-Min 200 EMA |
| *(and so on)* | *(one timeframe lower's 200 EMA)* |

**Additional Rules:**
- If a price breakdown occurs on any timeframe, check whether there is **support on the next higher timeframe** before acting.
- If a stock's price reaches the 200 EMA but has **not yet bounced or confirmed**, add it to the **Watch List** — monitor for a valid bounce confirmation before entering. (Do not act on the 200 EMA touch alone; wait for the bounce to confirm that the correction has ended and the trend is resuming.)

---

## Confirmation Tool — Fibonacci Retracement

Use Fibonacci retracement levels drawn from the last **swing high to swing low** (for an uptrend correction) to confirm that the correction has ended.

**Primary confluence levels to watch:**

| Level | Interpretation |
|---|---|
| **38.2%** | Shallow correction — strong underlying trend |
| **50.0%** | Standard correction — most common EMA confluence zone |
| **61.8%** | Deep correction — high-conviction reversal level |

> **Confluence rule:** When a Fibonacci level (38.2%, 50%, or 61.8%) aligns within 1–2% of the correction EMA (20/50/100/200), that overlap is a **high-confidence entry signal**. This alignment boosts signal confidence in the scanner.

The 23.6% and 78.6% levels are informational only — they are not primary entry triggers.

---

## Entry Rules & Risk Management

### Entry Trigger
Do not enter at a raw EMA touch alone. Wait for **bounce confirmation** — a candle that closes back above the correction EMA after touching it. The GATE breakout (price breaking the upper boundary of the GATE formation) is the primary entry trigger.

### Minimum Risk-Reward Requirement (S-2)
Every trade must have a **minimum Risk-Reward ratio of 1.5:1 at the first target (T1)** before entry.

> Trades with RR < 1.5 at T1 are rejected regardless of how clean the setup looks.

### Stop Loss Distance Cap (S-3)
The stop loss must be **within 12% of the entry price**. If the natural SL (smaller-TF EMA200) is more than 12% away, the setup is invalid — do not enter.

### Liquidity Filter (S-4)
Only trade stocks that meet both criteria:
- **Price ≥ ₹20** (avoid penny stocks)
- **20-day average volume ≥ 100,000 shares** (adequate liquidity for entry and exit)

### Trailing Stop Loss Plan (S-5)
Post-entry position management:

| Event | Action |
|---|---|
| **T1 hit** | Move stop loss to entry price (break-even) |
| **T2 hit** | Trail stop loss up to T1 level |
| **T3 hit** | Exit the full position, or trail stop to last swing low on the signal timeframe |

---

## Pyramiding (Position Building)

- Add to your position as the stock price increases by a set percentage.
- **Add quantity at every valid GATE formation** that forms during the trend.

---

## Targets by Timeframe

| Timeframe | Holding Period (Trading Days) | Minimum Target |
|---|---|---|
| Monthly | 8 – 12 Years | 8x – 12x |
| Weekly | 1.75 – 3 Years | 2x – 3x |
| Daily | 5 – 8 Months | 50% – 70% |
| 4 Hr | ~4 Months | 35% – 40% |
| 3 Hr | ~3 Months | 30% – 35% |
| 2 Hr | ~2 Months | 25% – 30% |
| 1 Hr | 1 – 1.5 Months | 20% – 25% |
| 30 Min | 20 – 25 Days | 15% – 20% |
| 15 Min | 12 – 15 Days | 15% |
| 10 Min | 10 – 12 Days | 10% |
| 5 Min | 5 – 7 Days | 5% – 7% |
| 3 Min | ~2 Days | 3% – 4% |
| 1 Min | ~1 Day | 3% – 4% |

---

## Chart Reading Process

**Read charts top-down first, then drill down for entry timing.**

**Step 1 — Top-down context (large → small):** Start from Monthly → Weekly → Daily to identify the dominant trend direction. This establishes whether you are looking for long or short setups.

**Step 2 — Entry timing (small → large):** Once the macro direction is confirmed, scan smaller timeframes (1Hr → 4Hr → Daily) for a GATE formation or a correction completing at an EMA. The smallest timeframe where the GATE appears is the **leading timeframe**; the next-larger timeframe is used to **confirm the signal**.

> A signal on the 5-minute chart that contradicts the Weekly trend should be ignored — higher timeframes always override lower timeframes for direction.

---

## Stock Watchlist System

Maintain **5 active stock lists** at all times:

| # | List Name | Purpose |
|---|---|---|
| 1 | **Investment List** | Long-term holdings based on monthly/weekly timeframe setups |
| 2 | **Buy Trade List** *(Swing)* | Medium-term swing trades based on daily/weekly setups |
| 3 | **Short-Term List** *(Position)* | Positional trades based on intraday-to-daily timeframes |
| 4 | **Watch List** | Stocks approaching key setups; monitoring for entry |
| 5 | **Ignore List** | Stocks with broken structure (all major timeframes bearish), failed RR setups, or illiquid names — do not trade |

---

*This strategy is built on the principle that price and time corrections are predictable, measurable, and tradeable. Master the correction — and the trend will take care of itself.*
