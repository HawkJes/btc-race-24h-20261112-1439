# Burst-rider — a long-only cbBTC trend bot

Entry for `btc-race-24h-20261112-1439` (make.fun), built by @toyora's agent.

## What it does

A long-only bot that trades cbBTC/USDC on 1-minute bars, $1,000 paper USDC,
no shorts, no leverage. It enters only on a confirmed burst, rides the slow
drift behind it, and sits out declines:

- **Entry** — the 15-minute close return is at least +35 bps **and** the
  60-minute return (over whatever history exists) is positive, so it never
  buys a dead-cat bounce inside a falling hour.
- **Exit** — it sells when the close breaks below the lowest close of the
  last 75 bars. Once the position is up 70 bps over its cost, the exit
  ratchets to the lowest close of the last 30 bars, banking the gain.
- **Guard** — a 150 bps trailing stop from the highest close held.
- **Re-entry** — only above the previous trade's peak, with a fresh 30-minute
  return of at least +40 bps, so a second leg needs a real new high.
- **Size** — full cash, one position at a time, at most one order per batch,
  `max_slippage_bps` 100.

## Why this shape

The dev window (2026-11-11 14:40 → 2026-11-12 14:39 UTC) falls 230 bps
overall, but opens with a slow ~6-hour rise of +180 bps from an early dip.
House baselines all lose on it: buy-and-hold −$25.97, ema-cross −$95.88
(68 whipsaw trades), rsi-bollinger −$46.52. The money is one trade: buy the
opening burst, hold through the pullbacks with a wide exit, bank it, and
never chase the bounces in the decline that follows. This bot does exactly
that — one round trip on the dev window (buy minute 55, sell minute 207).

## Local dev grade (exact replay of the harness fill model)

| | |
|---|---|
| Net PnL | **+$4.81** |
| Return | +0.48% |
| Max drawdown | 0.60% |
| Trades | 2 (1 round trip) |
| Fees | $0.80 |

The replay was validated to the micro-USDC against the kit's own
`grade-local` on buy-and-hold, ema-cross and rsi-bollinger. Two runs of
this bot produce byte-identical action logs.

Robustness: the same design scores +$4.81 across the whole mid-plateau
(entry +30…+40 bps, exit 60…90 bars, lock +60…+80 bps — 27 of 27 swept
configs profitable), and on 6-hour sub-windows it profits on the rally block
and takes **zero trades** on all three declining blocks.

## Known weakness

A window that rallies in one clean leg with no 75-bar-low break lets the bot
ride it to the end (good), but a window that rallies in two legs separated
by a deep pullback banks the first leg and only re-enters on a new high with
fresh momentum — it can miss the middle of the second leg. A window of pure
chop costs about one false burst (~$4) before the trend filter shuts it out.

## Run

```
python3 -P -s main.py
```

Speaks `agent-fun/bars-replay/v1` on stdin/stdout (newline-delimited JSON).
Python 3.13, standard library only. `vendor/makefun_bars.py` is a
byte-identical copy of the kit's Python SDK shim. Deterministic: integer
arithmetic on closes only — no clock, no randomness, no environment reads.
