"""Burst-rider: a long-only cbBTC trend bot for agent-fun/bars-replay/v1.

Idea (from the dev window's own shape, 2026-11-11/12): BTC's 24h moves come
as short bursts inside slow multi-hour drifts, with 30-80 bps pullbacks that
kill tight stops and dead-cat bounces that kill dip-buyers. So this bot:

  * enters only on a confirmed burst -- the 15-minute close return is at
    least +35 bps AND the 60-minute return (over whatever history exists) is
    positive, so it never buys a bounce inside a falling hour;
  * rides the drift with a wide Donchian exit -- it sells when the close
    breaks below the lowest close of the last 75 bars, and once the position
    is up 70 bps over its cost the exit ratchets to the lowest close of the
    last 30 bars, banking the gain instead of giving it back;
  * keeps a 150 bps trailing stop from the peak as a catastrophe guard;
  * re-enters only above the previous trade's peak, with a fresh 30-minute
    return of at least +40 bps, so a second leg needs a real new high;
  * trades its full cash, one position at a time, at most one order a batch.

Everything is integer arithmetic on closes (bps, truncated toward zero by
Python's // on non-negative numerators and floored on the rare negative one
-- deterministic either way, same input gives same output). No clock, no
randomness, no environment reads, no network: two runs on the same bars
produce byte-identical replies.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"

# Entry: 15-bar return at least this many bps, with the 60-bar trend positive.
ENTRY_LOOKBACK = 15
ENTRY_MIN_BPS = 35
TREND_LOOKBACK = 60
# Exit: close below the lowest close of the last EXIT_DONCH bars.
EXIT_DONCH = 75
# Once up LOCK_BPS over cost, the exit ratchets to LOCK_DONCH bars.
LOCK_BPS = 70
LOCK_DONCH = 30
# Catastrophe guard: sell 150 bps below the peak close held.
TRAIL_BPS = 150
# Re-entry: price above the previous trade's peak and a 30-bar return of
# at least this many bps.
REENTRY_LOOKBACK = 30
REENTRY_MIN_BPS = 40
MAX_SLIPPAGE_BPS = 100

closes = []
peak = None
gate_high = None
locked = False


def _ret_bps(new, old):
    """Return of new over old in basis points (integer math)."""
    return (new - old) * 10000 // old


def _trend_ok():
    """True when the 60-bar return over available history is positive."""
    n = min(TREND_LOOKBACK, len(closes) - 1)
    if n <= 0:
        return True
    return _ret_bps(closes[-1], closes[-n - 1]) > 0


def _donchian_low(span):
    """Lowest close of the last `span` bars, excluding the current one."""
    if len(closes) <= span:
        return None
    return min(closes[-span:-1])


def on_batch(state, batch):
    global peak, gate_high, locked
    if state.warming_up:
        return []
    bar = None
    for b in batch.get("bars", []):
        if b.get("symbol") == SYMBOL:
            bar = b
            break
    if bar is None:
        return []
    close = int(bar["c"])
    closes.append(close)

    held = state.positions.get(SYMBOL)
    if held is not None and held.qty > 0:
        peak = close if peak is None else max(peak, close)
        if close * 10000 <= peak * (10000 - TRAIL_BPS):
            gate_high = peak
            locked = False
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        if not locked:
            value_now = state.value(SYMBOL, held.qty)
            if value_now * 10000 >= held.cost * (10000 + LOCK_BPS):
                locked = True
        span = LOCK_DONCH if locked else EXIT_DONCH
        low = _donchian_low(span)
        if low is not None and close < low:
            gate_high = peak
            locked = False
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    if len(closes) <= ENTRY_LOOKBACK:
        return []
    if _ret_bps(close, closes[-ENTRY_LOOKBACK - 1]) < ENTRY_MIN_BPS:
        return []
    if not _trend_ok():
        return []
    if gate_high is not None:
        if close <= gate_high:
            return []
        if len(closes) <= REENTRY_LOOKBACK:
            return []
        if _ret_bps(close, closes[-REENTRY_LOOKBACK - 1]) < REENTRY_MIN_BPS:
            return []
    peak = close
    locked = False
    return [{"side": "buy", "symbol": SYMBOL,
             "notional_quote_units": state.cash,
             "max_slippage_bps": MAX_SLIPPAGE_BPS}]


makefun_bars.run(on_batch)
