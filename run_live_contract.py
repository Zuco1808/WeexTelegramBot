"""Dump contract spec za jedan simbol (veličina ugovora, min, preciznost).

python run_live_contract.py            # BTCUSDT
python run_live_contract.py --symbol ETHUSDT
"""
import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def find_symbol_dicts(obj, needle):
    """Rekurzivno nadi dict-ove ciji bilo koji string-value sadrzi needle."""
    found = []
    if isinstance(obj, dict):
        if any(isinstance(v, str) and needle in v.lower() for v in obj.values()):
            found.append(obj)
        for v in obj.values():
            found += find_symbol_dicts(v, needle)
    elif isinstance(obj, list):
        for v in obj:
            found += find_symbol_dicts(v, needle)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    args = ap.parse_args()
    load_env(os.path.join(ROOT, ".env"))
    from weexbot.weex import RestWeexClient

    client = RestWeexClient.from_env()
    data = client.exchange_info(args.symbol)

    out_path = os.path.join(ROOT, "data", "exchange_info.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Pun JSON spremljen: {out_path}")
    print("Top-level kljucevi:", list(data) if isinstance(data, dict) else type(data))

    base = args.symbol[:-4].lower() if args.symbol.lower().endswith("usdt") else args.symbol.lower()
    matches = find_symbol_dicts(data, base + "usdt")
    # uzmi onaj koji ima najvise polja (contract config, ne samo {asset:...})
    matches = [m for m in matches if len(m) > 2]
    print(f"\n=== Contract zapis(i) za {args.symbol} ===")
    for m in matches[:3]:
        print(json.dumps(m, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
