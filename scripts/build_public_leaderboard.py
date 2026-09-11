#!/usr/bin/env python3.11
"""build_public_leaderboard.py — publiczny ranking portfeli (wersja 2).

ZASADA NADRZĘDNA: publikujemy DOWÓD, nie wynik. Portfel z 2 pozycjami i +100%
ROI to nie "najlepszy trader", to szum — nie może stać na czele zestawienia.

Co liczymy:
  - jedna obserwacja = jedna POZYCJA (portfel × rynek), nie pojedyncze wypełnienie
    (118 wypełnień jednego zakładu = 1 decyzja, nie 118 zwycięstw/porażek)
  - ROI = ΣPnL / Σkapitał (wagi pieniężne)
  - Z = (WR − avg_cena) / sqrt(avg_cena(1−avg_cena)/n)
  - **ROI_dolna = 5. percentyl bootstrapu** (1000 resamplów pozycji) — konserwatywna
    estymata: "nawet w pesymistycznym scenariuszu tyle zostało"
  - ewidencja: conclusive (n≥10 i Z≥1.5) / suggestive (n≥10 i Z≥1) / insufficient

Ranking główny sortuje po ROI_dolna — czyli za dowodem, nie za szczęściem.
Pełna lista (także przegrywający i małe próby) jest publikowana zawsze.

Użycie: python3.11 scripts/build_public_leaderboard.py --out /sciezka/data/
"""
import json, math, os, random, sqlite3, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "data", "forward_shadow.db")
WATCH = os.path.join(HERE, "data", "forward_shadow_watchlist.json")

MIN_POS_HEADLINE = 8      # minimum do rankingu głównego
BOOT = 1000               # resamplów bootstrapu
random.seed(42)


def bootstrap_roi_lower(ps, q=0.05, boot=BOOT):
    """5. percentyl ROI z bootstrapu pozycji (PnL i kapitał parowane)."""
    if len(ps) < 3:
        return None
    pairs = [(p["pnl"], p["cap"]) for p in ps if p["cap"] > 0]
    if len(pairs) < 3:
        return None
    n = len(pairs)
    rois = []
    for _ in range(boot):
        sp = spc = 0.0
        for _ in range(n):
            pnl, cap = pairs[random.randrange(n)]
            sp += pnl; spc += cap
        if spc > 0:
            rois.append(sp / spc)
    if not rois:
        return None
    rois.sort()
    return rois[int(q * len(rois))]


def evidence_label(n, z, roi):
    if n >= 10 and z >= 1.5 and roi > 0:
        return "conclusive"
    if n >= 10 and z >= 1.0:
        return "suggestive"
    if n >= 10:
        return "no edge"
    return "insufficient"


def build():
    watch = {}
    try:
        for w in json.load(open(WATCH)):
            watch[(w.get("wallet") or "").lower()] = w
    except Exception as e:
        print(f"[pub] watchlist error: {e}", flush=True)

    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = c.execute("""
        SELECT wallet, conditional_id, cat, SUM(won=1) AS won_any, COUNT(*) AS fills,
               SUM(pnl) AS pnl, SUM(usdc) AS cap,
               SUM(size*price)/NULLIF(SUM(size),0) AS vwap,
               MIN(ts) AS first_ts, MAX(ts) AS last_ts
        FROM shadow_trades WHERE resolved=1 AND usdc > 0
        GROUP BY wallet, conditional_id
    """).fetchall()
    totals = c.execute("SELECT COUNT(*), COUNT(DISTINCT wallet), SUM(resolved=1), "
                       "MIN(ts), MAX(ts) FROM shadow_trades").fetchone()

    pos = defaultdict(list)
    for wallet, cid, cat, won_any, fills, pnl, cap, vwap, f_ts, l_ts in rows:
        pos[wallet].append({"cat": cat or "other", "won": 1 if (won_any or 0) > 0 else 0,
                            "fills": fills, "pnl": pnl or 0.0, "cap": cap or 0.0,
                            "px": vwap or 0.0, "first_ts": f_ts, "last_ts": l_ts})

    wallets = []
    for wallet, ps in pos.items():
        wl = watch.get(wallet.lower(), {})
        n = len(ps)
        cap = sum(p["cap"] for p in ps)
        if cap <= 0 or n == 0:
            continue
        wins = sum(p["won"] for p in ps)
        pnl = sum(p["pnl"] for p in ps)
        wr = wins / n
        avgpx = sum(p["px"] for p in ps) / n
        roi = pnl / cap
        z = (wr - avgpx) / math.sqrt(avgpx * (1 - avgpx) / n) if 0 < avgpx < 1 else 0.0
        lo = bootstrap_roi_lower(ps)
        cats = defaultdict(float)
        for p in ps:
            cats[p["cat"]] += p["cap"]
        dom = max(cats.items(), key=lambda kv: kv[1])[0] if cats else "other"
        wallets.append({
            "wallet": wallet,
            "alias": wl.get("alias") or wallet[:8],
            "category": dom,
            "positions": n,
            "fills": sum(p["fills"] for p in ps),
            "wins": wins,
            "winrate": round(wr, 4),
            "avg_price": round(avgpx, 4),
            "roi_forward": round(roi, 4),
            "roi_lower": round(lo, 4) if lo is not None else None,
            "z": round(z, 2),
            "pnl": round(pnl, 1),
            "capital": round(cap, 1),
            "hist_roi": (round(wl["hist_roi"] / 100, 4)
                         if wl.get("hist_roi") is not None else None),
            "hist_z": wl.get("hist_z"),
            "hist_positions": wl.get("hist_n"),
            "evidence": evidence_label(n, z, roi),
            "headline": n >= MIN_POS_HEADLINE,
            "first_seen": time.strftime("%Y-%m-%d", time.gmtime(min(p["first_ts"] for p in ps))),
            "last_trade": time.strftime("%Y-%m-%d", time.gmtime(max(p["last_ts"] for p in ps))),
        })

    head = [w for w in wallets if w["headline"]]
    head.sort(key=lambda w: -(w["roi_lower"] if w["roi_lower"] is not None else -9))
    rest = [w for w in wallets if not w["headline"]]
    rest.sort(key=lambda w: -w["roi_forward"])

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "watchlist_started": time.strftime("%Y-%m-%d", time.gmtime(totals[3] or 0)),
        "min_positions_headline": MIN_POS_HEADLINE,
        "totals": {
            "wallets_tracked": len(wallets),
            "positions_resolved": len(rows),
            "fills_resolved": totals[2] or 0,
            "headline_wallets": len(head),
            "profitable": sum(1 for w in wallets if w["roi_forward"] > 0),
            "conclusive": sum(1 for w in wallets if w["evidence"] == "conclusive"),
        },
        "methodology": [
            "<b>One observation = one position</b> (wallet × market), never a single trade fill. "
            "118 fills of one bet is one decision, not 118 wins.",
            "<b>ROI = Σ P&amp;L / Σ capital</b>, capital-weighted. Never an average of percentages — "
            "averaging returns lets a $2 bet outweigh a $20,000 one.",
            "<b>Z</b> = (win rate − average price) / √(p(1−p)/n). A wallet buying at 80¢ needs an "
            "80% win rate just to break even; Z measures the gap against that baseline.",
            "<b>ROI lower bound</b> = 5th percentile of 1,000 bootstrap resamples of the wallet's "
            "own positions. A conservative estimate: what it would still show in a bad scenario.",
            "The main ranking sorts by <b>ROI lower bound, not ROI</b> — this rewards evidence "
            "rather than luck.",
            "Minimum <b>%d resolved positions</b> to enter the main ranking. Smaller samples are "
            "listed below with a label, not hidden." % MIN_POS_HEADLINE,
            "All resolutions come from <b>official Polymarket settlements</b> (Gamma API), not from "
            "price proxies — a proxy can disagree with the real outcome by 12%.",
            "<b>We publish every tracked wallet</b>, including the losing ones. Removing them would "
            "turn this into advertising.",
            "<b>No signals for sale, no fees, no positions of our own</b>, no affiliation with Polymarket.",
        ],
        "wallets": head + rest,
    }
    return out


def main():
    out_dir = HERE
    args = sys.argv[1:]
    if "--out" in args:
        out_dir = args[args.index("--out") + 1]
    data = build()
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, "leaderboard.json")
    json.dump(data, open(p, "w"), indent=1)
    t = data["totals"]
    print(f"[pub] {p}")
    print(f"[pub] portfeli={t['wallets_tracked']} pozycji={t['positions_resolved']} "
          f"rozliczeń={t['fills_resolved']} | ranking={t['headline_wallets']} "
          f"| conclusive={t['conclusive']} | profitable={t['profitable']}")


if __name__ == "__main__":
    main()
