"""Faza 0: ekstraktor poruka iz Telegram HTML izvoza.

Kljucna razlika u odnosu na stari ekstrakt_html.py:
  - <br> tagove pretvara u '\\n' PRIJE get_text() -> cuva strukturu poruke
    (entry/stop/take vise nisu zalijepljeni jedan na drugi).
  - hvata i id i datum poruke (za kasniju korelaciju update poruka).
  - NE ogranicava na 50 poruka - izvlaci sve (Faza 0 = sto veci dataset).

Izlaz (folder ./data):
  - messages_all.jsonl   : SVE poruke {id, date, text}
  - signals_sample.txt   : citljiv uzorak poruka koje lice na signale

Pokretanje:
    python extract_messages.py
    python extract_messages.py --html "C:\\put\\do\\messages.html" --max 0
"""
import argparse
import json
import os
import sys

from bs4 import BeautifulSoup

DEFAULT_HTML = r"C:\Users\korisnik\Downloads\Telegram Desktop\ChatExport_2026-06-06\messages.html"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

SIGNAL_KW = ("entry", "tp", "sl", "stop", "take", "target",
             "long", "short", "price", "leverage")


def extract_messages(html_path: str) -> list[dict]:
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    messages: list[dict] = []
    last_date = None
    for msg in soup.select("div.message"):
        mid = msg.get("id", "")
        date_div = msg.select_one(".date")
        date = date_div.get("title") if date_div else last_date
        last_date = date

        text_div = msg.select_one("div.text")
        if text_div is None:
            continue
        # <br> -> novi red, da polja ostanu odvojena
        for br in text_div.find_all("br"):
            br.replace_with("\n")
        body = text_div.get_text().strip()
        if not body:
            continue
        messages.append({"id": mid, "date": date, "text": body})
    return messages


def looks_like_signal(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in SIGNAL_KW)


def main() -> int:
    ap = argparse.ArgumentParser(description="Telegram HTML -> JSONL ekstraktor (Faza 0)")
    ap.add_argument("--html", default=DEFAULT_HTML, help="Putanja do messages.html")
    ap.add_argument("--max", type=int, default=0,
                    help="Maksimalan broj signal-poruka u uzorku (0 = sve)")
    args = ap.parse_args()

    if not os.path.exists(args.html):
        print(f"GRESKA: HTML fajl nije pronaden:\n  {args.html}")
        print("Provjeri putanju ili je proslijedi preko --html \"...\".")
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Citam: {args.html}")
    messages = extract_messages(args.html)
    print(f"Izvuceno ukupno poruka: {len(messages)}")

    # 1) sve poruke -> JSONL
    all_path = os.path.join(OUT_DIR, "messages_all.jsonl")
    with open(all_path, "w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    # 2) citljiv uzorak signala
    signals = [m for m in messages if looks_like_signal(m["text"])]
    if args.max and args.max > 0:
        signals = signals[: args.max]
    sample_path = os.path.join(OUT_DIR, "signals_sample.txt")
    with open(sample_path, "w", encoding="utf-8") as f:
        for i, m in enumerate(signals, 1):
            f.write(f"--- PORUKA {i} (id={m['id']}, {m['date']}) ---\n{m['text']}\n"
                    f"-------------------\n\n")

    print(f"Spremljeno:\n  {all_path}  ({len(messages)} poruka)")
    print(f"  {sample_path}  ({len(signals)} signal-poruka)")
    print("\nSljedeci korak:  python analyze.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
