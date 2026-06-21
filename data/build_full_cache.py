"""
Full-universe EDGAR gold crawl -> data/gold_cache_full.json.

Iterates the entire SEC ticker universe (~10.4k) and caches every company that
yields a valid FY2022 gross margin (banks/REITs/utilities auto-skip). Writes to a
SEPARATE file so the stable S&P 500 gold_cache.json (used by the deployed env) is
never disturbed mid-crawl. Incremental saves + resume make interruption safe.

    python -m quant_firm.data.build_full_cache      # ~50 min, throttled

When it finishes, merge into the live cache and redeploy:
    python - <<'PY'
    import json,pathlib
    base=pathlib.Path("quant_firm/data")
    a=json.load(open(base/"gold_cache.json")); b=json.load(open(base/"gold_cache_full.json"))
    a.update(b); json.dump(a, open(base/"gold_cache.json","w"), indent=1)
    print("merged ->", len(a), "entries")
    PY
"""
from __future__ import annotations
import json
import pathlib
import time

from quant_firm.data import edgar

YEARS = [2022]                       # core query; S&P 500 cache already has FY2021 for YoY
OUT = pathlib.Path(__file__).with_name("gold_cache_full.json")
SAVE_EVERY = 100


def main():
    tickers = sorted(edgar._ticker_map())
    cache: dict = {}
    if OUT.exists():
        try:
            cache = json.load(open(OUT))
        except Exception:
            cache = {}
    done = {k.split(":")[0] for k in cache}
    print(f"universe: {len(tickers)} tickers | resuming with {len(cache)} entries "
          f"({len(done)} tickers already attempted)", flush=True)

    ok = skip = 0
    for i, t in enumerate(tickers):
        if t in done:
            continue
        for y in YEARS:
            try:
                cache[f"{t}:{y}"] = edgar.gross_margin(t, y)
                ok += 1
            except Exception:
                skip += 1
            time.sleep(0.25)          # ~average under SEC's ~10 req/s fair-access
        done.add(t)
        if i % SAVE_EVERY == 0:
            json.dump(cache, open(OUT, "w"))
            valid = len({k.split(":")[0] for k in cache if k.endswith(":2022")})
            print(f"  {i:5}/{len(tickers)}  valid_cos={valid} ok={ok} skip={skip}", flush=True)

    json.dump(cache, open(OUT, "w"), indent=0)
    valid = sorted({k.split(":")[0] for k in cache if k.endswith(":2022")})
    print(f"\nDONE: {len(cache)} entries, {len(valid)} valid FY2022 companies", flush=True)


if __name__ == "__main__":
    main()
