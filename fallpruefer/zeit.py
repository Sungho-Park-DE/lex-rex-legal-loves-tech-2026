"""Time, dates and money — the only place any of them is produced.

`heute()` exists from the first line of the build on purpose (14 §10): every
user-visible date calculation goes through it, so pinning the clock to the
pitch date is a config flip and not a rewrite. Event logs use `jetzt()`, which
is always the real clock — the demo Stichtag must never falsify an audit trail.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from fallpruefer.konfig import konfig

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


def heute() -> date:
    """The day the program reckons from. `stichtag_modus: demo` pins it to
    `demo_stichtag`; anything else uses the real clock."""
    k = konfig()
    if k.stichtag_modus == "demo":
        return parse_datum(k.demo_stichtag)
    return date.today()


def stichtag() -> date:
    """Alias of `heute()` for the places that display it as „Stand …"."""
    return heute()


def jetzt() -> str:
    """Real wall-clock timestamp for the event log — never the demo Stichtag."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_datum(wert: str | date | None) -> date | None:
    if wert is None or isinstance(wert, date):
        return wert
    s = str(wert).strip()
    # A well-formed but impossible date („2026-13-01", „31.02.2026") is not a
    # date. It must drop out like any other unusable value — the validator's
    # promise is that a bad value cannot reach the engine, not that it takes
    # the request down with it.
    try:
        if m := _ISO.match(s):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := _DE.match(s):
            return date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None
    return None


def datum_de(wert: str | date | None) -> str:
    d = parse_datum(wert)
    return d.strftime("%d.%m.%Y") if d else ""


def datum_iso(wert: str | date | None) -> str:
    d = parse_datum(wert)
    return d.isoformat() if d else ""


def betrag_de(wert: float | int | str | None) -> str:
    if wert is None:
        return ""
    try:
        x = float(str(wert).replace(",", "."))
    except ValueError:
        return str(wert)
    return f"{x:,.2f} €".replace(",", " ").replace(".", ",").replace(" ", ".")


def parse_betrag(wert: float | int | str | None) -> float | None:
    """German amounts as they stand in a document („29,90", „1.234,50 EUR")."""
    if wert is None:
        return None
    if isinstance(wert, (int, float)):
        return float(wert)
    s = re.sub(r"[^\d,.\-]", "", str(wert))
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def tage_addieren(d: date, tage: int) -> date:
    return d + timedelta(days=tage)


def tage_zwischen(a: date, b: date) -> int:
    return (b - a).days


def monate_zwischen(a: date, b: date) -> int:
    """Whole months from `a` to `b`; a partial month does not count."""
    monate = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        monate -= 1
    return monate
