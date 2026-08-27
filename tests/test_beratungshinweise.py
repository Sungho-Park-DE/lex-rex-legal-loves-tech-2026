"""T-H1 / T-H6 — die Sätze aus Franz' Lieferungen, die ausdrücklich keine
Prüfpunkte sind.

Zwei Harvest-Posten, die wie Einzelfälle aussahen und dieselbe fehlende Fläche
waren: `24` §5.2 und §2.1 sagen beide wörtlich „das ist ein Beratungshinweis,
kein Prüfpunkt", und es gab nirgends einen Ort dafür — `config.texte` hält vier
feste Strings, `pruefumfang` hängt an Prüfpunkten, `offene_punkte` ist „was noch
fehlt". Ein Hinweis ist keines davon.

Die Hinweise laufen durch **dieselbe Regelgrammatik und denselben Kontext** wie
die Rechtsbehelfe. Das ist der Punkt und wird hier auch geprüft: zwei Kopien
desselben Kontextblocks wären zwei Kontexte, die auseinanderlaufen, und der
Unterschied fiele erst auf, wenn eine Bedingung an einer Stelle greift und an
der anderen nicht.
"""

from __future__ import annotations

import json

import pytest

from fallpruefer import pipeline as pl
from fallpruefer.dokumente import laden
from fallpruefer.konfig import WURZEL
from fallpruefer.schema import schema_laden
from fallpruefer.vokabular import Hinweisart

FAELLE = WURZEL / "demo" / "faelle"


def _lauf(verzeichnis, dateien, case_id):
    ticket = json.loads((verzeichnis / "ticket.json").read_text(encoding="utf-8"))
    dokumente = [laden(verzeichnis / n, f"D{i}") for i, n in enumerate(dateien, start=1)]
    return pl.verarbeiten(pl.fall_anlegen(case_id, ticket, dokumente))


@pytest.fixture(scope="module")
def schema():
    return schema_laden("preiserhoehung")


# --------------------------------------------------------------------------
# das Schema selbst
# --------------------------------------------------------------------------


# Hinweise, die niemand von außen je vorgelegt bekommen hat — dieselbe
# Ausnahme wie `UNSERE_EIGENEN` in `test_zuschreibung.py`, und aus demselben
# Grund. H6 und H7 sind der Störfall-Beat (14 §7): sie berichten, was das
# Programm beim Kreuzprüfen bemerkt hat, und behaupten bewusst keine
# Rechtsfolge. Ein fremder Name daran wäre die Falschzuschreibung, gegen die
# der ganze Entwurf gebaut ist — deshalb wird hier das Gegenteil geprüft.
UNSERE_EIGENEN = {"H6", "H7"}


def test_jeder_hinweis_ist_vollstaendig_und_zugeschrieben(schema):
    """Ein Hinweis ohne Zuschreibung wäre auf genau diesem Bildschirm die
    auffälligste Lücke: die Sätze H1 bis H5 sind Franz' Sätze, nicht unsere."""
    assert schema.beratungshinweise, "keine Beratungshinweise im Schema"
    for h in schema.beratungshinweise:
        assert h.id and h.titel.strip() and h.text.strip()
        assert isinstance(h.art, Hinweisart)
        if h.id in UNSERE_EIGENEN:
            assert not h.geprueft_von, (
                f"{h.id} ist unser eigener Hinweis — er darf nicht unter "
                f"fremdem Namen laufen"
            )
            continue
        assert h.geprueft_von, f"{h.id} trägt keine Zuschreibung"
        for f in h.geprueft_von:
            assert f.wer.strip() and f.beleg.strip() and f.umfang.strip()


def test_unsere_eigenen_hinweise_behaupten_keine_rechtsfolge(schema):
    """Der Preis der Ausnahme oben: ein Hinweis ohne Juristennamen darf kein
    Ergebnis behaupten, sondern nur berichten, was das Programm gesehen hat,
    und die Beraterin auffordern, selbst hinzusehen.

    Ohne diesen Test wäre `UNSERE_EIGENEN` eine Hintertür, durch die jede
    unbelegte Rechtsaussage auf den Schirm käme.
    """
    verboten = ("unwirksam", "wirksam", "Anspruch", "maßgeblich", "Sie können verlangen")
    for h in schema.beratungshinweise:
        if h.id not in UNSERE_EIGENEN:
            continue
        for wort in verboten:
            assert wort.lower() not in h.text.lower(), (
                f"{h.id} behauptet [{wort}] - ein Hinweis ohne Juristennamen "
                f"berichtet, er urteilt nicht"
            )


def test_kein_hinweis_behauptet_eine_norm_die_wir_nicht_haben(schema):
    """`anker` darf leer sein — und ist es bei H2 und H3 mit Absicht. Was
    dasteht, muss aber auflösbar sein, sonst rendert es `normbasis_fehlt`."""
    from fallpruefer.normbasis import normbasis

    nb = normbasis()
    bekannt = set(nb.gesetze) | set(nb.rechtsprechung)
    for h in schema.beratungshinweise:
        for a in h.anker:
            assert a.get("key") in bekannt, f"{h.id}: {a.get('key')} fehlt in der Normbasis"
            assert a.get("geprueft") is False, "kein Anker ist von einem Menschen bestätigt"


def test_die_zwei_hebel_stehen_als_frage_da_nicht_als_feststellung(schema):
    """H3 nennt § 309 Nr. 12 lit. b und § 312f Abs. 1 — beide hängen an
    Tatsachen, die wir gar nicht extrahieren (gibt es eine gebündelte
    Bestätigungsklausel? wo wurde unterschrieben?).

    Sie zu behaupten wäre falsch, sie wegzulassen wäre Verschwendung. Also
    stehen sie als Frage an die Beraterin da, und der Vorbehalt sagt warum.
    """
    h3 = schema.hinweis("H3")
    assert h3 is not None
    assert "?" in h3.titel and "?" in h3.text
    assert h3.geprueft_von[0].vorbehalt, "der Vorbehalt ist hier die halbe Aussage"
    assert not h3.anker, "die beiden Normen sind nicht in der Normbasis — kein Anker"


# --------------------------------------------------------------------------
# was in den Demofällen wirklich feuert
# --------------------------------------------------------------------------


def test_jeder_demofall_loest_mindestens_einen_hinweis_aus():
    """Ein Feld, das in allen Fixtures leer ist, ist von der Anzeigeseite her
    ungeprüft — die UI-Sitzung hat das am selben Abend an einem `Override`-Typ
    erlebt, dessen drei von vier Feldnamen es gar nicht gibt und den nie etwas
    gefüllt hat. Für diese Liste soll das nicht gelten."""
    faelle = [
        (FAELLE / "drehkreuz", ["schreiben.md", "agb.md", "vertrag.md"]),
        (FAELLE / "sauber_aktivpark", ["schreiben.md", "agb.md", "vertrag.md"]),
        (FAELLE / "nordlicht_agb_fehlen", ["schreiben.md"]),
        (FAELLE / "seepark_seite_fehlt", ["schreiben.md", "bedingungen_seite1.md", "vertrag.md"]),
    ]
    for i, (verzeichnis, dateien) in enumerate(faelle):
        fall = _lauf(verzeichnis, dateien, f"F-HINWEIS-{i}")
        assert fall.aktuelle_pruefung().beratungshinweise, f"{verzeichnis.name}: keine Hinweise"


def test_die_hinweise_haengen_am_fall_und_nicht_am_urteil():
    """Anders als die Rechtsbehelfe: `sauber_aktivpark` ist `wirksam` und
    bekommt trotzdem die SEPA-Warnung, weil sie nicht daran hängt, ob die
    Erhöhung hält, sondern daran, dass abgebucht werden wird. Genau deshalb
    ist es kein Prüfpunkt."""
    fall = _lauf(FAELLE / "sauber_aktivpark",
                 ["schreiben.md", "agb.md", "vertrag.md"], "F-HINWEIS-W")
    pruefung = fall.aktuelle_pruefung()
    assert pruefung.einordnung == "wirksam"
    assert "H1" in pruefung.beratungshinweise


def test_der_darlegungslast_hinweis_haengt_an_der_fehlenden_klausel():
    """H2 feuert, wenn P2 oder P5 auf FEHLT steht — und nur dann. Sonst wäre er
    ein Satz über einen Fall, in dem die Klausel vorliegt."""
    ohne_agb = _lauf(FAELLE / "nordlicht_agb_fehlen", ["schreiben.md"], "F-HINWEIS-A")
    assert "H2" in ohne_agb.aktuelle_pruefung().beratungshinweise

    vollstaendig = _lauf(FAELLE / "sauber_aktivpark",
                         ["schreiben.md", "agb.md", "vertrag.md"], "F-HINWEIS-B")
    assert "H2" not in vollstaendig.aktuelle_pruefung().beratungshinweise


def test_der_hinweis_verschwindet_wieder_wenn_die_unterlage_eintrifft():
    """Die Hinweise werden bei jedem Lauf neu bestimmt, nicht angesammelt."""
    fall = _lauf(FAELLE / "seepark_seite_fehlt",
                 ["schreiben.md", "bedingungen_seite1.md", "vertrag.md"], "F-HINWEIS-C")
    assert {"H2", "H3"} <= set(fall.aktuelle_pruefung().beratungshinweise)

    fall = pl.nachreichung(
        fall, [laden(FAELLE / "seepark_seite_fehlt" / "bedingungen_seite2_nachgereicht.md")])
    danach = set(fall.aktuelle_pruefung().beratungshinweise)
    assert "H2" not in danach and "H3" not in danach
    assert "H1" in danach, "die SEPA-Warnung hängt nicht an den Unterlagen"


def test_die_sepa_warnung_haengt_am_wirksamkeitsdatum_und_an_sonst_nichts():
    """Warum der Hinweis vorausschauend formuliert ist, und was das kostet.

    Erste Fassung feuerte erst, wenn der erhöhte Betrag schon abgebucht war
    (`wirksam_ab <= heute`). Gemessen: in **keinem** der vier Demofälle ist das
    so — `wirksam_ab` liegt überall nach dem Stichtag. Die Bedingung war damit
    sachlich richtig und der nützlichste Hinweis des Bestandes unsichtbar,
    obwohl in zwei von acht Fällen der Verbraucher von sich aus danach fragt.

    Statt eine Frist zu erfinden, damit er feuert, ist der Hinweis jetzt
    vorausschauend („sagen Sie es ihr, bevor sie fragt") und hängt nur noch
    daran, dass wir wissen, wann das Geld sich ändert.

    **Der Preis, damit er hier steht:** er feuert damit in dieser Fallgruppe
    praktisch immer. Das ist vertretbar — es ist die meistgestellte Frage im
    Bestand und der Schaden bei falscher Antwort ist ein Inkassoverfahren —
    aber es ist eine Setzung und keine Messung.

    Der Test prüft nur, was die Bedingung wirklich sagt: vorhanden → ja,
    nicht vorhanden → nein.
    """
    from fallpruefer.evaluator import Fallkontext
    from fallpruefer.regeln import auswerten

    h1 = schema_laden("preiserhoehung").hinweis("H1")
    fall = _lauf(FAELLE / "drehkreuz",
                 ["schreiben.md", "agb.md", "vertrag.md"], "F-HINWEIS-D")
    k = Fallkontext(fall=fall, schema=schema_laden("preiserhoehung"))
    assert auswerten(h1.wenn, k) is True

    # und ohne bekanntes Wirksamkeitsdatum feuert er nicht
    fall.fakten = [f for f in fall.fakten if f.feld_id != "erhoehungsschreiben.wirksam_ab"]
    k2 = Fallkontext(fall=fall, schema=schema_laden("preiserhoehung"))
    assert auswerten(h1.wenn, k2) is not True


# --------------------------------------------------------------------------
# der Kontext, den Hinweise und Rechtsbehelfe teilen
# --------------------------------------------------------------------------


def test_hinweise_und_rechtsbehelfe_sehen_denselben_kontext():
    """Der ganze Sinn der Sparsamkeit: ein Hinweis bedingt gegen dieselben
    Größen wie ein Rechtsbehelf. Zwei Kopien des Kontextblocks wären zwei
    Kontexte, die auseinanderlaufen — und der Unterschied fiele erst auf, wenn
    eine Bedingung an einer Stelle greift und an der anderen nicht."""
    fall = _lauf(FAELLE / "nordlicht_agb_fehlen", ["schreiben.md"], "F-HINWEIS-K")
    schema = schema_laden("preiserhoehung")
    k = pl._ergebnis_kontext(fall, schema, fall.aktuelle_pruefung())

    for name in ("einordnung", "gerissene_stufe", "fehlt_unternehmen",
                 "fehlt_verbraucher", "berechnung.rueckforderung"):
        assert name in k.extra, f"{name} fehlt im geteilten Kontext"
    assert any(s.startswith("pruefpunkt.") for s in k.extra)


def test_der_brief_sagt_warum_das_unternehmen_liefern_muss():
    """T-H1s Kern. Das Auskunftsverlangen hat bis hierher gebeten, ohne einen
    Grund zu nennen. Der Grund steht jetzt drin — **ohne Paragraf**, wie der an
    den Originalen abgelesene VZ-Hausstil es verlangt (`22` §8: die reinen
    Inkassobriefe zitieren gar keine Norm und argumentieren über Beweislast)."""
    fall = _lauf(FAELLE / "nordlicht_agb_fehlen", ["schreiben.md"], "F-HINWEIS-BR")
    # Hauptvorschlag ist hier zu Recht die Nachforderung — verbraucherseitig
    # fehlt etwas (V-39). Das Auskunftsverlangen ist der zweite Vorschlag; die
    # Beraterin wählt ihn an Gate 4, wenn sie beim Unternehmen ansetzen will.
    pl.gate4_rechtsbehelf(fall, "bestreiten_nachweise_verlangen")
    brief = fall.rechtsbehelf.brief
    assert brief and brief.template_id == "musterbrief_auskunftsverlangen"
    assert "an Ihnen darzulegen" in brief.text
    assert "§" not in brief.text, "im Schreiben an das Unternehmen stehen keine Paragrafen"


def test_eine_id_ohne_hinweis_im_schema_nimmt_die_fallakte_nicht_mit():
    """Die Prüfung speichert IDs, das Schema hält die Texte — also gibt es den
    Zustand „gespeicherte ID, die es nicht mehr gibt".

    Er ist erreichbar: ein Jurist nimmt einen Hinweis aus der Datei, und
    jemand sieht sich eine **gespeicherte** Fallakte an, ohne sie neu laufen zu
    lassen. Beim Neu-Prüfen kann er nicht auftreten, weil die Liste bei jedem
    Lauf frisch bestimmt wird — genau deshalb fällt er ohne Test niemandem auf.

    Dasselbe Muster wie bei `pruefumfang`, dessen Projektion einen unbekannten
    Prüfpunkt schon überspringt (`ansicht._hero`). Hier über HTTP geprüft, weil
    das die Form ist, die ein Aufrufer wirklich hat.
    """
    from fastapi.testclient import TestClient

    from fallpruefer.api import app
    from fallpruefer.pipeline import fall_speichern

    fall = _lauf(FAELLE / "nordlicht_agb_fehlen", ["schreiben.md"], "F-HINWEIS-STALE")
    fall_speichern(fall)
    assert "H2" in fall.aktuelle_pruefung().beratungshinweise

    pfad = WURZEL / "schemas" / "preiserhoehung.json"
    sicherung = pfad.read_text(encoding="utf-8")
    try:
        daten = json.loads(sicherung)
        daten["beratungshinweise"] = [
            h for h in daten["beratungshinweise"] if h["id"] != "H2"
        ]
        pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")

        assert schema_laden("preiserhoehung").hinweis("H2") is None
        antwort = TestClient(app).get("/faelle/F-HINWEIS-STALE")
        assert antwort.status_code == 200, antwort.text
    finally:
        pfad.write_text(sicherung, encoding="utf-8")


def test_der_wirksam_zweig_bekommt_den_vorbehalt_zweimal_gesagt():
    """`26` §4.2 — Franz' Antwort auf „welches Schreiben bei wirksam?" enthielt
    fertigen Text, und er nennt **zwei** Orte: das Schreiben an das Unternehmen
    und den **Verwendungszweck der Überweisung**.

    Der zweite war nirgends. Er ist auch kein Brieftext, sondern eine Anweisung
    an die Beraterin — also ein Hinweis (H5). Der erste stand nur halb da: die
    Vorlage sagte „unter Vorbehalt der Rückforderung", Franz' Formel lautet
    „**ohne Anerkennung einer Rechtspflicht** und unter Vorbehalt der
    Rückforderung", und die weggelassene Hälfte ist die, die den Verzug
    ausschließt.

    Zusammen mit H1 ergibt das den Rat vollständig: nicht zurückbuchen (H1),
    sondern unter Vorbehalt zahlen — und zwar so (H5 + Musterschreiben).
    """
    from fallpruefer.pipeline import gate4_rechtsbehelf

    fall = _lauf(FAELLE / "sauber_aktivpark",
                 ["schreiben.md", "agb.md", "vertrag.md"], "F-VORBEHALT")
    pruefung = fall.aktuelle_pruefung()
    assert pruefung.einordnung == "wirksam"
    assert {"H1", "H5"} <= set(pruefung.beratungshinweise), \
        "gerade der wirksam-Zweig braucht beide Hälften des Rats"

    gate4_rechtsbehelf(fall, "auskunftsverlangen_vorbehalt")
    text = fall.rechtsbehelf.brief.text
    assert "ohne Anerkennung einer Rechtspflicht" in text
    assert "unter Vorbehalt der Rückforderung" in text


def test_der_vorbehalt_hinweis_schweigt_wo_widersprochen_wird():
    """Bei `wahrscheinlich unwirksam` ist der Rat ein anderer — widersprechen
    und zurückfordern. H5 dort auch anzuzeigen hieße, der Beraterin zwei Wege
    gleichzeitig zu empfehlen."""
    fall = _lauf(FAELLE / "drehkreuz",
                 ["schreiben.md", "agb.md", "vertrag.md"], "F-VORBEHALT-N")
    pruefung = fall.aktuelle_pruefung()
    assert pruefung.einordnung == "wahrscheinlich unwirksam"
    assert "H5" not in pruefung.beratungshinweise
