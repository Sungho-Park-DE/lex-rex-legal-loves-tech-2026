"""V-A1 — wer hat welchen Prüfpunkt fachlich entschieden.

Der eine Satz, auf dem das Produkt steht, ist „ein Jurist hat das bewertet".
Bis hierher hatte er im Artefakt kein einziges Beleg: `geprueft_von` stand als
leere Liste im Schema, wurde von `schema.py` geparst und danach von nichts mehr
gelesen.

Die Zuschreibung sitzt **am einzelnen Prüfpunkt**, und die Tests hier halten
genau das fest. Ein Name über der ganzen Datei wäre bequemer und wäre falsch:
P8b und P14 sind unsere eigenen Punkte, die Franz nie vorgelegen haben, und eine
pauschale Abnahme würde sie mitdecken. Das ist dieselbe Falschzuschreibung,
gegen die der ganze Entwurf gebaut ist — nur eine Ebene höher.
"""

from __future__ import annotations

import json

import pytest

from fallpruefer.konfig import WURZEL
from fallpruefer.schema import schema_laden

SCHEMA_DIR = WURZEL / "schemas"
ALLE = sorted(p.stem for p in SCHEMA_DIR.glob("*.json") if not p.stem.startswith("_"))

# Punkte, die niemand ausserhalb des Teams je vorgelegt bekommen hat. Sie dürfen
# keine fremde Zuschreibung tragen, solange das so ist. P8c (§ 309 Nr. 13
# lit. b) steht bewusst NICHT hier: Paulina hat ihn in Runde 3 unabhängig
# beantwortet (`29` §3) und trägt ihn; Franz' Antwort dazu widersprach sich
# selbst (`26` §5) und deckt ihn nicht. P8d (Laufzeit/Verlängerung, § 309
# Nr. 9) ist der aus P8 herausgelöste Arm: Franz hat § 308 Nr. 5 lit. a
# bestätigt, nie § 309 Nr. 9 — der Punkt trägt deshalb keinen Namen.
UNSERE_EIGENEN = {"preiserhoehung": {"P8b", "P8d", "P14"}}


@pytest.mark.parametrize("fallgruppe_id", ALLE)
def test_kein_schema_traegt_eine_pauschale_abnahme(fallgruppe_id):
    """Das schemaweite `geprueft_von` bleibt leer, bis jemand das ganze
    Prüfschema abgenommen hat — und niemand hat das."""
    schema = schema_laden(fallgruppe_id)
    assert schema.geprueft_von == [], (
        f"{fallgruppe_id}: ein Name über der ganzen Datei deckt auch die "
        f"Prüfpunkte mit, die derjenige nie gesehen hat"
    )


@pytest.mark.parametrize("fallgruppe_id", ALLE)
def test_jede_zuschreibung_sagt_wer_wann_woher_und_worueber(fallgruppe_id):
    """Eine Zuschreibung ohne Beleg ist eine Behauptung.

    `beleg` sagt, wo es steht, `umfang` sagt, **was genau** bestätigt wurde —
    ohne den zweiten Teil liest sich jede Zuschreibung als Abnahme des ganzen
    Prüfpunkts samt unserer Umsetzung.
    """
    for pp in schema_laden(fallgruppe_id).pruefpunkte:
        for f in pp.geprueft_von:
            for feld in ("wer", "am", "beleg", "umfang"):
                assert getattr(f, feld).strip(), f"{fallgruppe_id}/{pp.id}: {feld} ist leer"
            assert len(f.am) == 10 and f.am[4] == f.am[7] == "-", \
                f"{fallgruppe_id}/{pp.id}: {f.am} ist kein ISO-Datum"


@pytest.mark.parametrize("fallgruppe_id", ALLE)
def test_unsere_eigenen_pruefpunkte_tragen_keinen_fremden_namen(fallgruppe_id):
    for pp in schema_laden(fallgruppe_id).pruefpunkte:
        if pp.id in UNSERE_EIGENEN.get(fallgruppe_id, set()):
            assert not pp.geprueft_von, (
                f"{fallgruppe_id}/{pp.id} ist unser eigener Punkt — er darf "
                f"nicht unter fremdem Namen laufen"
            )


def test_der_stand_wird_im_motor_gerechnet_und_stimmt():
    """Die Anzeige soll die Zahl bekommen, nicht selbst zählen (Absprache mit
    der UI-Sitzung). Sie macht Abwesenheit als Zahl lesbar, statt dreizehn
    Negativabzeichen nebeneinanderzustellen, die zum Wegsehen erziehen."""
    schema = schema_laden("preiserhoehung")
    bestaetigt, gesamt = schema.fachpruefung_stand()

    assert gesamt == len(schema.pruefpunkte)
    assert bestaetigt == sum(1 for p in schema.pruefpunkte if p.geprueft_von)
    assert 0 < bestaetigt < gesamt, (
        "entweder ist die Zuschreibung verschwunden oder jemand hat pauschal "
        "abgenommen — beides will dieser Test sehen"
    )


def test_die_zuschreibung_haelt_die_datei_und_den_kontrakt_zusammen():
    """`geprueft_von` ist Schemadaten wie alles andere: es steht in beiden
    Dateien oder in keiner. Sonst liest der Jurist im Kontrakt eine Abnahme,
    die in der laufenden Datei nicht steht (oder umgekehrt)."""
    datei = (SCHEMA_DIR / "preiserhoehung.json").read_text(encoding="utf-8")
    aus_datei = json.loads(datei)
    mit_zuschreibung = {
        pp["id"] for pp in aus_datei["pruefpunkte"] if pp.get("geprueft_von")
    }
    assert mit_zuschreibung, "keine einzige Zuschreibung in der Datei"
    # test_kontrakt_identitaet hält die Byte-Gleichheit; hier geht es darum,
    # dass der geladene Baum dasselbe sagt wie der rohe Text.
    geladen = {p.id for p in schema_laden("preiserhoehung").pruefpunkte if p.geprueft_von}
    assert geladen == mit_zuschreibung
