# Forward Tested

Forward-tested Polymarket trader verification. We pick wallets, publish them, then publish
what happened next — **including the ones that lose money.**

Live: **https://mateuszslowinski92-creator.github.io/forward-tested/**

## Why this exists

Most prediction-market leaderboards rank by profit. That has two problems:

1. **Profit is not edge.** A wallet that bet big once and won looks identical to a wallet with
   a repeatable process — until it isn't.
2. **Failures get deleted.** Rankings show winners; the wallets that blew up quietly disappear.

This project tracks a fixed watchlist and reports its **forward** results, losers included.
Every wallet on the list is still on the list.

## Method

- **One observation = one position** (wallet × market), never a single trade fill. 118 fills of
  one bet is one decision, not 118 wins.
- **ROI = Σ P&L / Σ capital** (capital-weighted). Never an average of percentages — averaging
  returns lets a $2 bet outweigh a $20,000 one.
- **Z** = (win rate − average price) / √(p(1−p)/n). Buying at 80¢ requires an 80% win rate to
  break even; Z measures the gap against that baseline.
- **ROI lower bound** = 5th percentile of 1,000 bootstrap resamples of the wallet's own
  positions — a conservative estimate.
- The main ranking sorts by **ROI lower bound, not ROI**: evidence over luck.
- All resolutions come from **official Polymarket settlements** (Gamma API), never price proxies.
- Minimum 8 resolved positions for the main ranking; smaller samples are labelled, not hidden.

## What this is not

- Not a signal service. Nothing is sold, no fees, no positions of our own.
- Not financial advice. Forward performance does not guarantee anything.
- Not affiliated with Polymarket. All data is public.

## Files

| path | what |
|---|---|
| `index.html` | the page (single file, no build step, no dependencies) |
| `data/leaderboard.json` | the dataset — open, no auth |
| `scripts/build_public_leaderboard.py` | generator (bootstrap CIs, position aggregation) |

## Reproduce

The generator reads a shadow-tracking SQLite database:

```
shadow_trades(wallet, conditional_id, cat, side, price, size, usdc, ts,
              resolved, won, pnl, title, slug)
```

One row per trade fill; the script aggregates to positions itself. Then:

```bash
python3.11 scripts/build_public_leaderboard.py --out data/
```

## Corrections

Every number here is reproducible from public data. If you think one is wrong, open an issue
with the wallet address and the position you dispute — corrections are published, not hidden.

## License

MIT
