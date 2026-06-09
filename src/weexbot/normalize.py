"""Sloj 1: normalizacija sirovog teksta prije klasifikacije i ekstrakcije.

Cilj: ukloniti smetnje (emoji, zero-width, razni crtice) i ujednaciti brojeve
tako da regex ekstraktori rade nad cistim, jednolinijskim stringom.
"""
import re

# en-dash, em-dash, minus, figure-dash -> obicni hyphen
_DASHES = {"–": "-", "—": "-", "−": "-", "‒": "-", "‐": "-"}

# zarez kao separator tisucica: ukloni samo kad iza slijede TOCNO 3 znamenke
# pa nije-znamenka ili kraj. Tako "4,750" -> "4750", a "0,3%" (decimalni
# zarez, samo 1 znamenka iza) ostaje netaknut.
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?:\D|$))")


def normalize(raw: str) -> str:
    if raw is None:
        return ""
    t = raw
    for bad, good in _DASHES.items():
        t = t.replace(bad, good)
    t = t.replace("​", "")           # zero-width space (Telegram cesto ubaci)
    # Ukloni sve ne-ASCII (emoji, simboli) -> zamijeni razmakom da se rijeci ne zalijepe
    t = re.sub(r"[^\x00-\x7f]+", " ", t)
    t = _THOUSANDS.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()    # vise praznina/novih redova -> jedan razmak
    return t
