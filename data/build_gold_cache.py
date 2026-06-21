"""
Build the hermetic EDGAR gold cache for the S&P 500 (FY2022 + FY2021).

Only companies that tag revenue + COGS/gross profit yield a valid gross margin
(banks/REITs/utilities are structurally skipped). The derived gold per company is
tiny, so the cache stays small; SEC fair-access is respected with a throttle.

    python -m quant_firm.data.build_gold_cache
"""
from __future__ import annotations
import json
import pathlib
import time

import requests

from quant_firm.data import edgar

YEARS = [2022, 2021]
SP500_CSV = ("https://raw.githubusercontent.com/datasets/"
             "s-and-p-500-companies/main/data/constituents.csv")
OUT = pathlib.Path(__file__).with_name("gold_cache.json")


def sp500_tickers() -> list[str]:
    txt = requests.get(SP500_CSV, headers=edgar.HEADERS, timeout=30).text
    out = []
    for row in txt.strip().splitlines()[1:]:
        sym = row.split(",")[0].strip().strip('"')
        out.append(sym.replace(".", "-"))   # SEC uses BRK-B, not BRK.B
    return out


def main():
    tickers = sp500_tickers()
    print(f"S&P 500 list: {len(tickers)} tickers", flush=True)
    cache: dict = {}
    ok = skip = 0
    for i, t in enumerate(tickers):
        for y in YEARS:
            try:
                cache[f"{t}:{y}"] = edgar.gross_margin(t, y)
                ok += 1
            except Exception:
                skip += 1
            time.sleep(0.3)                  # ~3 req/s headroom under SEC's ~10/s
        if i % 25 == 0:
            print(f"  {i:3}/{len(tickers)}  ok={ok} skip={skip}", flush=True)
    json.dump(cache, open(OUT, "w"), indent=1)
    valid = sorted({k.split(":")[0] for k in cache if k.endswith(":2022")})
    print(f"\nwrote {len(cache)} entries -> {OUT}", flush=True)
    print(f"valid FY2022 companies: {len(valid)}", flush=True)
    print("sample:", valid[:25], flush=True)


if __name__ == "__main__":
    main()
