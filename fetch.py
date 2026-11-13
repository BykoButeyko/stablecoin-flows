"""Download raw data into data/ and print the sha256 of each file.

python fetch.py
"""
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DATA = Path(__file__).parent / "data"
UA = {"User-Agent": "Mozilla/5.0 (research script)"}
START = datetime(2019, 12, 1, tzinfo=timezone.utc)


def get(url, **params):
    for attempt in range(4):
        r = requests.get(url, params=params, headers=UA, timeout=120)
        if r.status_code == 200:
            return r
        time.sleep(2 * (attempt + 1))
    r.raise_for_status()


def save(name, obj):
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(obj), encoding="utf-8")


def defillama():
    # The full asset file is ~22 MB, mostly per-chain detail I don't use.
    # I keep only the asset-level daily totals (see PLAN.md, pitfall 2).
    for asset_id, name in (("1", "usdt"), ("2", "usdc")):
        d = get(f"https://stablecoins.llama.fi/stablecoin/{asset_id}").json()
        rows = [{"date": t["date"],
                 "circulating": t["circulating"].get("peggedUSD"),
                 "unreleased": (t.get("unreleased") or {}).get("peggedUSD")
                 if isinstance(t.get("unreleased"), dict) else None}
                for t in d["tokens"]]
        save(f"{name}.json", rows)


def binance():
    out, t = [], int(START.timestamp() * 1000)
    while True:
        x = get("https://api.binance.com/api/v3/klines", symbol="BTCUSDT",
                interval="1d", startTime=t, limit=1000).json()
        if not x:
            break
        out += [[k[0], k[4]] for k in x]  # open time ms, close
        t = x[-1][0] + 86_400_000
        if len(x) < 1000:
            break
    save("binance.json", out)


def coinbase():
    out, t = [], START
    end = datetime.now(timezone.utc)
    while t < end:
        t2 = min(t + timedelta(days=300), end)
        x = get("https://api.exchange.coinbase.com/products/BTC-USD/candles",
                granularity=86400, start=t.isoformat(), end=t2.isoformat()).json()
        out += [[k[0], k[4]] for k in x]  # open time s, close
        t = t2
        time.sleep(0.4)
    save("coinbase.json", sorted(set(map(tuple, out))))


def hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(DATA.glob("*.json"))}


if __name__ == "__main__":
    defillama()
    binance()
    coinbase()
    print(f"fetched {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    for k, v in hashes().items():
        print(k, v)
