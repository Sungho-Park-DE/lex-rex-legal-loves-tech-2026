"""The adapter's post-processing — the layer B1 found a defect in.

`anthropic_adapter.py` had 0 % coverage: the only test that touched it was the
live replay, which skips without a key. `_nachbereiten` is a pure function, so
it can be pinned without a network call — and it is where the first live run
found a real bug.
"""

from __future__ import annotations

from fallpruefer.adapter.anthropic_adapter import AnthropicAdapter, LiveExtraktion

SPEC = {"felder": [
    {"feld_id": "erhoehungsschreiben.begruendung", "typ": "text"},
    {"feld_id": "agb.betroffene_leistungen", "typ": "liste_text"},
]}


def _nach(felder: list[dict]) -> dict[str, object]:
    roh = LiveExtraktion.model_validate({"felder": [
        {"zitat": "x", "seite": 1, **f} for f in felder
    ]})
    aus = AnthropicAdapter._nachbereiten("extract_fields", roh, SPEC)
    return {f["feld_id"]: f["wert"] for f in aus["felder"]}


def test_ein_textfeld_mit_semikolon_bleibt_text():
    """The bug the first live run found (B1, `a3ac3c8`).

    The prompt says „Listen mit Semikolon getrennt", and the old code applied
    that to every string containing a semicolon — without looking at the field
    spec. German prose contains semicolons, so this real live answer became a
    list, and `_wert_parsen` turned it back into a string with `str()`, leaving
    a Python repr as the value of a field that is interpolated into the trace,
    into `satz_nein` and into letters.

    Derivation: `erhoehungsschreiben.begruendung` is `typ: text` in
    `schemas/preiserhoehung.json`, so `15` §1 says its value is the text — the
    document's own wording, unsplit.
    """
    werte = _nach([{"feld_id": "erhoehungsschreiben.begruendung",
                    "wert": "Gestiegene Kosten: Energie um 9,4 Prozent; gewichtet 4,2 Prozent"}])
    wert = werte["erhoehungsschreiben.begruendung"]
    assert isinstance(wert, str)
    assert wert == "Gestiegene Kosten: Energie um 9,4 Prozent; gewichtet 4,2 Prozent"
    assert not str(wert).startswith("["), "ein Python-Repr als Wert eines Textfeldes"


def test_ein_listenfeld_mit_semikolon_wird_weiterhin_getrennt():
    """The convention itself must survive the fix — `liste_text` is exactly
    what the prompt's semicolon rule is for."""
    werte = _nach([{"feld_id": "agb.betroffene_leistungen",
                    "wert": "Sauna; Kurse; Getränke"}])
    assert werte["agb.betroffene_leistungen"] == ["Sauna", "Kurse", "Getränke"]


def test_ohne_semikolon_bleibt_ein_listenfeld_ein_einelement():
    werte = _nach([{"feld_id": "agb.betroffene_leistungen", "wert": "Sauna"}])
    assert werte["agb.betroffene_leistungen"] == ["Sauna"]


def test_ein_feld_das_die_soll_liste_nicht_kennt_wird_nicht_getrennt():
    """A field id the Soll does not declare cannot be `liste_text`, so it must
    not be split on a guess. The deterministic validator drops it afterwards
    either way — but it must not be *reshaped* on the way there."""
    werte = _nach([{"feld_id": "agb.gibt_es_nicht", "wert": "a; b"}])
    assert werte["agb.gibt_es_nicht"] == "a; b"


def test_klassifikation_wird_nicht_nachbearbeitet():
    from fallpruefer.adapter.anthropic_adapter import LiveKlassifikation
    roh = LiveKlassifikation.model_validate(
        {"dokumenttyp": "agb", "konfidenz": 0.9, "begruendung": "a; b"})
    aus = AnthropicAdapter._nachbereiten("classify_doc", roh, SPEC)
    assert aus["begruendung"] == "a; b"


def test_der_cachesschluessel_haengt_nur_an_dem_was_das_modell_sieht():
    """Ein Feld zu viel in `feld_eingabe` entwertet **alle vier** Caches.

    Der Schlüssel ist `hash(dokumenttyp + Seitentext + Feldspezifikation)`. Die
    Feldspezifikation ist bewusst eine **Aufzählung** und kein `model_dump()`:
    sonst zöge jede Ergänzung am `Feld`-Modell den Cache mit — und der Bruch
    fiele nicht hier auf, sondern am Demotag, wenn `nur_cache` nichts findet.

    Beinahe passiert: V-23 hat `wert_labels` an `Feld` gehängt. Das ist reine
    Anzeige, das Modell antwortet mit Codes — und es steht zu Recht nicht in
    der Liste. Nachgesehen statt gehofft, und jetzt festgehalten.
    """
    from fallpruefer.adapter.cache_adapter import feld_eingabe
    from fallpruefer.schema import Feld, schema_laden

    ERWARTET = {"feld_id", "typ", "werte", "beschreibung", "zitat_pflicht", "pflicht"}
    felder = schema_laden("preiserhoehung").dokumenten_soll.dokumente[0].felder
    assert felder, "keine Felder — der Test misst nichts"
    for eintrag in feld_eingabe(felder):
        assert set(eintrag) == ERWARTET, (
            "die Feldspezifikation im Cacheschlüssel hat sich geändert — "
            "damit sind alle Caches ungültig. Vier Cache-Werkzeuge neu laufen "
            f"lassen (21 §3 P8) oder das Feld hier herausnehmen: {set(eintrag) ^ ERWARTET}"
        )

    # ein reines Anzeigefeld darf den Schlüssel nicht bewegen
    from fallpruefer.adapter.basis import eingabe_hash

    ohne = Feld(feld_id="x", typ="enum", werte=["a"])
    mit = Feld(feld_id="x", typ="enum", werte=["a"], wert_labels={"a": "A"})
    assert eingabe_hash({"f": feld_eingabe([ohne])}) == eingabe_hash({"f": feld_eingabe([mit])})
