#!/usr/bin/env python3
"""
THE SWORD 23 — DETERMINISTISCHER BACKTEST (MINUTEN-SCALE)
=========================================================
Vincent Weber | 3-6-9 Universal Neutrality Framework

Backtestet die 23/77-Mechanik aus sword_23_77.py — aber sauber:
  - Decision-Core 1:1 portiert (vote_3, π, Volume-Phase, Vote-Stabilität,
    SLEEP/ACTIVE-Zustandsautomat).
  - Deterministischer Replay statt WebSocket: 1m-Basis → 3/9/27/81m.
    Die 1/3/9/27/81-Geometrie bleibt, nur die Basiseinheit ist Minute
    statt Sekunde (Sekunden-Klines gibt es bei Bybit-REST nicht).
  - Event-Zeit statt time.time() → reproduzierbar.
  - ECHTES Pro-Kerzen-Volumen (live wurde fälschlich volume24h benutzt).
  - Taker-Fees im PnL — bei einem Flip-Stil DIE entscheidende Größe.

Usage:
  python3 sword23_backtest.py                 # BTCUSDT, 30 Tage, 0.055% Taker
  python3 sword23_backtest.py BTCUSDT 60      # 60 Tage
  python3 sword23_backtest.py ETHUSDT 30 0.06 # anderes Symbol/Fee
  python3 sword23_backtest.py --selftest      # synthetische Daten, kein Netz
"""

import math, time, sys, random
from datetime import datetime, timezone, timedelta

PI = math.pi

# Geometrie: Basis = 1 Minute. Wie im Live-Engine 1/3/9/27/81, nur Minuten.
BASE_INTERVAL = "1"        # Bybit-Kline-Intervall der Basis
DECISION_EVERY = 9         # alle 9 Basiseinheiten ein Vote (= 9 Minuten)
DEFAULT_TAKER_FEE = 0.055  # % pro Seite (Bybit Perp Taker)
MAX_HOLD_MIN = 4 * 60      # Sicherheits-Exit nach 4h (wie Live)

# ============================================================
# DECISION-CORE — 1:1 aus sword_23_77.py
# ============================================================

def vote_3(candles):
    if len(candles) < 3: return 0
    up = sum(1 for c in candles[-3:] if c["close"] > c["open"])
    if up >= 2: return 1    # LONG
    if up <= 1: return -1   # SHORT
    return 0

def kb2zahl(c):
    if not c: return 0
    r = float(c[-1])
    for i in range(len(c)-2, -1, -1):
        r = c[i] + (1.0/r if r != 0 else 0)
    return r

def is_pi_active(candles):
    """π in den Wendepunkt-Intervallen der letzten Kerzen?"""
    if len(candles) < 20:
        return False
    swings = []
    for i in range(2, len(candles)-2):
        h, l = candles[i]["high"], candles[i]["low"]
        if (h >= candles[i-1]["high"] and h >= candles[i+1]["high"] and
            h >= candles[i-2]["high"] and h >= candles[i+2]["high"]):
            swings.append(("H", i))
        elif (l <= candles[i-1]["low"] and l <= candles[i+1]["low"] and
              l <= candles[i-2]["low"] and l <= candles[i+2]["low"]):
            swings.append(("L", i))
    filtered = []
    for s in swings:
        if not filtered or filtered[-1][0] != s[0]:
            filtered.append(s)
    if len(filtered) < 4:
        return False
    intervals = [filtered[i+1][1] - filtered[i][1] for i in range(len(filtered)-1)]
    targets = [("π", PI, 0.01), ("2π", 2*PI, 0.01), ("π²", PI**2, 0.01)]
    for lb in range(3, min(8, len(intervals)+1)):
        c = intervals[-lb:]
        if 0 in c: continue
        try: z = kb2zahl(c)
        except: continue
        for name, tgt, me in targets:
            if abs(z - tgt) / tgt < me:
                return True
    return False

def volume_acceleration(candles_9, sma_period=3):
    """Geglättetes Volume-Momentum + Beschleunigung (2n²)."""
    if len(candles_9) < sma_period + 3:
        return "neutral", 0
    vols = [c["vol"] for c in candles_9[-(sma_period + 4):]]
    if max(vols) == 0:
        return "neutral", 0
    sma = [sum(vols[i:i+sma_period]) / sma_period
           for i in range(len(vols) - sma_period + 1)]
    if len(sma) < 3:
        return "neutral", 0
    M = [sma[i] - sma[i-1] for i in range(1, len(sma))]
    A = [M[i] - M[i-1] for i in range(1, len(M))]
    if not A:
        return "neutral", 0
    avg_vol = sum(vols) / len(vols)
    threshold = 0.01 * avg_vol
    recent_A = A[-1]
    if recent_A > threshold:
        return "aufbau", recent_A
    elif recent_A < -threshold:
        return "abbau", recent_A
    return "neutral", recent_A

def volume_exhausted(candles_9, confirm_periods=3, sma_period=3):
    """Erschöpfung = 2. Ableitung confirm_periods lang negativ, vorher positiv."""
    if len(candles_9) < sma_period + confirm_periods + 3:
        return False
    vols = [c["vol"] for c in candles_9[-(sma_period + confirm_periods + 4):]]
    if max(vols) == 0:
        return False
    sma = [sum(vols[i:i+sma_period]) / sma_period
           for i in range(len(vols) - sma_period + 1)]
    if len(sma) < confirm_periods + 3:
        return False
    M = [sma[i] - sma[i-1] for i in range(1, len(sma))]
    A = [M[i] - M[i-1] for i in range(1, len(M))]
    if len(A) < confirm_periods + 1:
        return False
    if not all(a < 0 for a in A[-confirm_periods:]):
        return False
    if not any(a > 0 for a in A[:-confirm_periods]):
        return False
    return True

def vote_stable(vote_history, window=9, threshold=3):
    if len(vote_history) < window:
        return False, None
    s = sum(vote_history[-window:])
    if abs(s) > threshold:
        return True, ("LONG" if s > 0 else "SHORT")
    return False, None

# ============================================================
# BYBIT-LOADER (bewährt aus pi.py / sword_v3.py)
# ============================================================

def fetch(symbol, interval, limit=1000, end_ms=None):
    import requests
    params = {"category":"linear","symbol":symbol,"interval":interval,"limit":limit}
    if end_ms: params["end"] = end_ms
    try:
        r = requests.get("https://api.bybit.com/v5/market/kline",
                         params=params, timeout=10).json()
        if r.get("retCode") != 0: return []
        return [{"date":datetime.fromtimestamp(int(x[0])/1000, tz=timezone.utc),
                 "open":float(x[1]),"high":float(x[2]),"low":float(x[3]),
                 "close":float(x[4]),"vol":float(x[5])} for x in r["result"]["list"]]
    except Exception as e:
        print(f"  fetch-Fehler: {e}")
        return []

def fetch_all(symbol, interval, days):
    all_d = []
    end = int(time.time()*1000)
    start = int((time.time()-days*86400)*1000)
    cur = end
    b = 0
    while cur > start:
        b += 1
        rows = fetch(symbol, interval, 1000, cur)
        if not rows: break
        all_d.extend(rows)
        cur = int(min(r["date"] for r in rows).timestamp()*1000)-1
        if b % 20 == 0:
            print(f"  ... {len(all_d)} Kerzen geladen", flush=True)
        time.sleep(0.05)
    seen, uniq = set(), []
    for d in all_d:
        k = d["date"].isoformat()
        if k not in seen: seen.add(k); uniq.append(d)
    return sorted(uniq, key=lambda x: x["date"])

def aggregate(base, factor):
    """Nicht-überlappende Blöcke: factor Basis-Kerzen → eine höhere Kerze."""
    out = []
    for i in range(0, len(base) - factor + 1, factor):
        g = base[i:i+factor]
        out.append({
            "date": g[0]["date"],
            "open": g[0]["open"],
            "high": max(c["high"] for c in g),
            "low":  min(c["low"]  for c in g),
            "close": g[-1]["close"],
            "vol":  sum(c["vol"]  for c in g),
        })
    return out

# ============================================================
# DETERMINISTISCHER REPLAY DER 23/77-STATE-MACHINE
# ============================================================

def run_backtest(base_1m, taker_fee=DEFAULT_TAKER_FEE, max_hold_min=MAX_HOLD_MIN):
    """
    Spielt den SLEEP/ACTIVE-Automaten kausal über die History.
    Entscheidung an jedem abgeschlossenen 9m-Block j.
    """
    c3  = aggregate(base_1m, 3)
    c9  = aggregate(base_1m, 9)
    c27 = aggregate(base_1m, 27)
    c81 = aggregate(base_1m, 81)

    state = "SLEEP"
    position = entry_price = entry_j = None
    vote_history = []
    trades = []
    capital = 100.0
    active_blocks = 0   # 9m-Blöcke im Markt (für Zeit-im-Markt-Quote)

    n_blocks = len(c9)
    for j in range(n_blocks):
        # Die drei 3m-Kerzen, die 9m-Block j bilden:
        if 3*j + 3 > len(c3):
            break
        block_3 = c3[3*j : 3*j+3]
        price = c9[j]["close"]

        # Vote auf die drei 3m-Kerzen
        vote_history.append(vote_3(block_3))

        # Kausal verfügbare höhere Kerzen (nur abgeschlossene Blöcke)
        n27 = (j + 1) // 3
        n81 = (j + 1) // 9
        c9_avail  = c9[:j+1][-12:]
        pi_27 = is_pi_active(c27[:n27]) if n27 >= 20 else False
        pi_81 = is_pi_active(c81[:n81]) if n81 >= 20 else False
        pi_active = pi_27 or pi_81

        vol_phase, _ = volume_acceleration(c9_avail)
        is_stable, stable_dir = vote_stable(vote_history)

        if state == "SLEEP":
            # Alle drei Bedingungen → IMPULS
            if pi_active and vol_phase == "aufbau" and is_stable and stable_dir:
                state = "ACTIVE"
                position = stable_dir
                entry_price = price
                entry_j = j
        else:  # ACTIVE
            active_blocks += 1
            exit_reason = None
            if volume_exhausted(c9_avail):
                exit_reason = "VOL_EXHAUST"
            elif not is_stable:
                exit_reason = "VOTE_UNSTABLE"
            elif is_stable and stable_dir != position:
                exit_reason = "VOTE_FLIP"
            elif (j - entry_j) * DECISION_EVERY >= max_hold_min:
                exit_reason = "MAX_HOLD"

            if exit_reason:
                if position == "LONG":
                    pnl = (price - entry_price) / entry_price * 100
                else:
                    pnl = (entry_price - price) / entry_price * 100
                pnl_net = pnl - 2 * taker_fee   # Entry + Exit Taker
                capital *= (1 + pnl_net/100)
                trades.append({
                    "entry_date": c9[entry_j]["date"],
                    "exit_date":  c9[j]["date"],
                    "dir": position,
                    "entry": entry_price,
                    "exit":  price,
                    "pnl_gross": pnl,
                    "pnl_net":   pnl_net,
                    "cap": capital,
                    "reason": exit_reason,
                    "held_min": (j - entry_j) * DECISION_EVERY,
                })
                state, position, entry_price, entry_j = "SLEEP", None, None, None

    return {
        "trades": trades, "capital": capital,
        "active_blocks": active_blocks, "total_blocks": n_blocks,
        "taker_fee": taker_fee,
    }

# ============================================================
# AUSWERTUNG
# ============================================================

def report(res, label=""):
    trades = res["trades"]
    total = len(trades)
    cap = res["capital"]
    print(f"\n{'='*70}")
    print(f"ERGEBNISSE — 23/77 Backtest {label}")
    print(f"{'='*70}")
    print(f"Taker-Fee:    {res['taker_fee']:.3f}% / Seite ({2*res['taker_fee']:.3f}% Round-Trip)")
    print(f"Trades:       {total}")
    if total == 0:
        mkt = res["active_blocks"] / res["total_blocks"] * 100 if res["total_blocks"] else 0
        print(f"Zeit im Markt: {mkt:.1f}% (Ziel ~23%) — keine geschlossenen Trades.")
        print("Hinweis: 23/77 ist selektiv; bei kurzer History/ruhigem Markt "
              "kann das Gate (π+Volume+Vote) selten alle drei gleichzeitig öffnen.")
        return

    wins = sum(1 for t in trades if t["pnl_net"] > 0)
    wr = wins/total*100
    gross_cap = 100.0
    for t in trades:
        gross_cap *= (1 + t["pnl_gross"]/100)

    mkt = res["active_blocks"] / res["total_blocks"] * 100 if res["total_blocks"] else 0
    avg_w = sum(t["pnl_net"] for t in trades if t["pnl_net"] > 0)/max(wins,1)
    losses = total - wins
    avg_l = sum(t["pnl_net"] for t in trades if t["pnl_net"] <= 0)/max(losses,1)

    peak, max_dd = 100.0, 0.0
    for t in trades:
        peak = max(peak, t["cap"])
        max_dd = max(max_dd, (peak - t["cap"])/peak*100)

    print(f"Wins:         {wins} ({wr:.1f}%)")
    print(f"Kapital NET:  ${cap:.2f} ({cap-100:+.1f}%)")
    print(f"Kapital GROSS:${gross_cap:.2f} ({gross_cap-100:+.1f}%)  ← ohne Fees")
    print(f"Fee-Drag:     {gross_cap-cap:+.2f} $ ({total} Trades × {2*res['taker_fee']:.3f}%)")
    print(f"Ø Win:        {avg_w:+.3f}%   Ø Loss: {avg_l:+.3f}%")
    if avg_l != 0:
        print(f"Risk/Reward:  {abs(avg_w/avg_l):.2f}")
    print(f"Max Drawdown: {max_dd:.1f}%")
    print(f"Zeit im Markt:{mkt:.1f}% (Ziel ~23%)")
    avg_hold = sum(t["held_min"] for t in trades)/total
    print(f"Ø Haltezeit:  {avg_hold:.0f} min")
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    print(f"Exit-Gründe:  {reasons}")

    # Random-Baseline (gleiche Trades, zufällige Richtung) — netto
    rcaps = []
    for _ in range(300):
        rc = 100.0
        for t in trades:
            same = random.choice([True, False])
            g = t["pnl_gross"] if same else -t["pnl_gross"]
            rc *= (1 + (g - 2*res["taker_fee"])/100)
        rcaps.append(rc)
    avg_r = sum(rcaps)/len(rcaps)
    better = sum(1 for r in rcaps if r >= cap)
    print(f"\n--- RANDOM BASELINE (netto, 300 Sims) ---")
    print(f"  Ø Random:     ${avg_r:.2f}")
    print(f"  Sword besser: {100 - better/3:.0f}% der Fälle")

    show = trades[-15:]
    print(f"\n--- LETZTE {len(show)} TRADES (netto) ---")
    print(f"{'Entry':<17}{'Dir':>5}{'Entry$':>11}{'Exit$':>11}{'PnL':>8}{'Cap':>9} {'Held':>5} {'Why'}")
    print("-"*82)
    for t in trades[-15:]:
        m = "✓" if t["pnl_net"] > 0 else "✗"
        print(f"{t['entry_date'].strftime('%d.%m %H:%M'):<17}{t['dir']:>5}"
              f"${t['entry']:>9,.2f} ${t['exit']:>9,.2f} {t['pnl_net']:>+6.2f}% "
              f"${t['cap']:>7,.2f} {t['held_min']:>4}m {t['reason']} {m}")

# ============================================================
# SELFTEST — synthetische Daten, kein Netz nötig
# ============================================================

def synth_1m(n=8000, seed=42):
    """Random-Walk mit Vol-Schüben, damit das Gate gelegentlich öffnet."""
    random.seed(seed)
    out = []
    price = 60000.0
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        drift = math.sin(i/137.0) * 6 + math.sin(i/33.0) * 3
        step = random.gauss(drift, 25)
        o = price
        price = max(1.0, price + step)
        hi = max(o, price) + abs(random.gauss(0, 8))
        lo = min(o, price) - abs(random.gauss(0, 8))
        vol = abs(random.gauss(100, 30)) * (2.5 if (i//50) % 7 == 0 else 1.0)
        out.append({"date": t0 + timedelta(minutes=i),
                    "open": o, "high": hi, "low": lo, "close": price, "vol": vol})
    return out

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print(f"{'='*70}")
    print(f"THE SWORD 23 — 23/77 BACKTEST (Minuten-Scale, fee-aware)")
    print(f"{'='*70}")

    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        print("SELFTEST: 8000 synthetische 1m-Kerzen (kein Netz)\n")
        data = synth_1m()
        print(f"Basis: {len(data)} 1m | 3m:{len(aggregate(data,3))} "
              f"9m:{len(aggregate(data,9))} 27m:{len(aggregate(data,27))} "
              f"81m:{len(aggregate(data,81))}")
        res = run_backtest(data)
        report(res, "[SELFTEST]")
        sys.exit(0)

    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    fee = float(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_TAKER_FEE

    print(f"Symbol: {symbol} | Tage: {days} | Basis: {BASE_INTERVAL}m → 3/9/27/81m")
    print(f"Vote alle {DECISION_EVERY}m | Taker {fee}%/Seite | Max-Hold {MAX_HOLD_MIN}min\n")

    data = fetch_all(symbol, BASE_INTERVAL, days)
    if not data:
        print("Keine Daten. Netzwerk/Bybit prüfen — oder --selftest nutzen.")
        sys.exit(1)
    print(f"Geladen: {len(data)} 1m-Kerzen "
          f"({data[0]['date'].strftime('%d.%m %H:%M')} – {data[-1]['date'].strftime('%d.%m %H:%M')})")
    res = run_backtest(data, taker_fee=fee)
    report(res, f"[{symbol} {days}d]")
