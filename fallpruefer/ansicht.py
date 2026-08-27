"""Case object → view model. A projection, nothing more.

Everything here was already decided by the evaluator, the remedy ranking and
the letter renderer. This module reshapes, labels and de-tokenises — it never
computes a verdict, a deadline or a sentence. If you find yourself wanting an
`if` about legal meaning in this file, it belongs in `evaluator.py`.

De-tokenisation happens here because this is one of exactly the two local
places contract §4 allows it: the advisor display (the other is template fill).
"""

from __future__ import annotations

import re

from typing import Any

from fallpruefer import viewmodel as vm
from fallpruefer import zeit
from fallpruefer.evaluator import Fallkontext, formatieren
from fallpruefer.fall import Fall, Pruefung
from fallpruefer.konfig import konfig
from fallpruefer.pipeline import TICKET_DOK_ID
from fallpruefer.normbasis import normbasis
from fallpruefer.schema import Knoten, Schema, taxonomie
from fallpruefer.viewmodel import Vokabel
from fallpruefer.vokabular import (
    Ankerpruefstand,
    Badge,
    PROTOKOLL_SCHRITT,
    Briefstatus,
    Dokumenttyp,
    Einordnung,
    Herkunft,
    Lauftrigger,
    Leitfadenstatus,
    Kanal,
    Nachforderungsstatus,
    OffenerPunktArt,
    Protokollaktion,
    Quelle,
    Normrang,
    Rolle,
    Stufe,
    Zustand,
    label,
    ton,
)


def _zurueck(text: str, karte: dict[str, str]) -> str:
    """Advisor display — one of the two allowed re-identification points."""
    for token, klartext in karte.items():
        text = text.replace(token, klartext)
    return text


def _vok(wert) -> Vokabel | None:
    return None if wert is None else Vokabel.von(wert)


def _fallgruppe_vokabel(fallgruppe_id: str) -> Vokabel:
    tax = taxonomie().get(fallgruppe_id, {})
    return Vokabel(code=fallgruppe_id, label=tax.get("name", fallgruppe_id), tone="grau")


def _zitat(q, karte: dict[str, str]) -> vm.Zitat:
    return vm.Zitat(
        dok_id=q.dok_id, seite=q.seite,
        zitat=_zurueck(q.zitat_pseudonym, karte),
    )


def _anker(keys: list[str], schema: Schema, pruefpunkt_id: str) -> list[vm.Anker]:
    nb = normbasis()
    pp = schema.pruefpunkt(pruefpunkt_id)
    roh = {a.get("key"): a for a in (pp.anker if pp else []) if a.get("key")}
    aus: list[vm.Anker] = []
    for key in keys:
        e = nb.aufloesen(key, roh.get(key))
        aus.append(vm.Anker(
            key=e.key, label=e.label, ebene=_vok(e.ebene), status=_vok(e.status),
            geprueft=e.geprueft, aufgeloest=e.aufgeloest, kernaussage=e.kernaussage,
            text=e.text, url=e.url, stand=e.stand,
            pruefstand=_vok(
                Ankerpruefstand.GEPRUEFT if e.geprueft else Ankerpruefstand.UNGEPRUEFT
            ),
        ))
    return aus


def _strittige(fall: Fall, feld_id: str) -> list:
    return [f for f in fall.fakten
            if f.feld_id == feld_id and f.herkunft == Herkunft.STRITTIG]


def _feldzeile(f, feld_id: str, fall: Fall, schema: Schema) -> vm.VerwendetesFeld:
    annahme = next(
        (a.anzeige for a in schema.annahmen if a.id == f.annahme_id), None
    ) if f.annahme_id else None
    spec = schema.dokumenten_soll.feld(feld_id)
    return vm.VerwendetesFeld(
        feld_id=feld_id,
        feld_label=spec.label if spec and spec.label else None,
        wert_anzeige=formatieren(f.wert, schema, feld_id),
        herkunft=_vok(f.herkunft), badge=_vok(f.badge),
        verifiziert=f.verifiziert,
        zitat=_zitat(f.quelle, fall.pseudonyme) if f.quelle else None,
        annahme_anzeige=annahme,
    )


def _verwendet(erg, fall: Fall, k: Fallkontext, schema: Schema) -> list[vm.VerwendetesFeld]:
    """One row per fact — and when a field is `strittig`, one row per *side*.

    `Fallkontext._faktum` returns a single fact, which is right for the rule:
    the rule needs one value. It is wrong for the screen. A Leitfaden answer
    that contradicts a document leaves two facts on the same `feld_id`, both
    marked `strittig`, and the Prüfpunkt goes to WERTUNG *because* they
    disagree. Showing only the last of them printed „widersprüchlich belegt"
    next to one value and hid what it contradicted — the advisor was asked to
    resolve a conflict at Gate 3 whose other half was not on the screen.
    """
    aus: list[vm.VerwendetesFeld] = []
    gesehen: set[str] = set()
    for feld_id in erg.verwendet:
        massgeblich = k._faktum(feld_id)
        if massgeblich is None:
            continue
        gesehen.add(feld_id)
        strittige = _strittige(fall, feld_id)
        for f in (strittige if len(strittige) > 1 else [massgeblich]):
            aus.append(_feldzeile(f, feld_id, fall, schema))

    # Ein widersprüchliches Feld fällt aus `verwendet` heraus — der Wert ist
    # `verifiziert=False`, die Regel liest ihn nicht mehr, und der Evaluator
    # verbucht nur Gelesenes. Der Prüfpunkt geht korrekt auf WERTUNG, aber auf
    # dem Schirm stand „Bewertung nötig" und die beiden Aussagen, die sich
    # widersprechen, standen nirgends. Seit `strittige_felder` (Kontrakt §5)
    # sagt die Spur selbst, welche das sind; die Projektion liest es ab, statt
    # es aus `schema.eingaben` zu erraten. `missing` bleibt unberührt — das ist
    # die Sprache für „fehlt" und speist Gate 1; hier fehlt nichts, es ist zu
    # viel da. Die Liste wird auch wieder leer, wenn die Verbraucherin sich auf
    # den Wert der Unterlage korrigiert: die Zeilen müssen verschwinden können.
    # V-L1: „geprüft, nicht enthalten" — ein Faktum ohne Wert, aber mit Zitat,
    # sagt, wo das Modell gesucht hat. Ohne diese Zeile sähe ein leeres Feld
    # genauso aus wie ein nie gelesenes.
    for feld_id in erg.missing:
        if feld_id in gesehen:
            continue
        f = next((x for x in fall.fakten
                  if x.feld_id == feld_id and x.wert is None and x.quelle is not None), None)
        if f is None:
            continue
        gesehen.add(feld_id)
        zeile = _feldzeile(f, feld_id, fall, schema)
        zeile.wert_anzeige = "nicht enthalten — geprüft, siehe Zitat"
        aus.append(zeile)

    for feld_id in erg.strittige_felder:
        if feld_id in gesehen:
            continue
        gesehen.add(feld_id)
        aus.extend(_feldzeile(f, feld_id, fall, schema) for f in _strittige(fall, feld_id))
    return aus


def _trace(erg, fall: Fall, schema: Schema, k: Fallkontext) -> vm.TraceEintrag:
    pp = schema.pruefpunkt(erg.pruefpunkt_id)
    return vm.TraceEintrag(
        pruefpunkt_id=erg.pruefpunkt_id,
        titel=pp.titel if pp else erg.pruefpunkt_id,
        proposition=pp.proposition if pp else "",
        zustand=_vok(erg.zustand), rolle=_vok(pp.rolle if pp else Rolle.ERGAENZEND),
        # Trägt der Punkt das gelbe LLM-Badge, sagt das schon „Textverständnis" —
        # der graue Typ-Chip daneben wäre dieselbe Aussage in einer zweiten Zeile
        # (Team-Rückfrage 25 Aug). Der Tooltip des Badges erklärt es.
        typ=_vok(pp.typ) if (pp and pp.typ and erg.badge != Badge.LLM_BEFUND) else None,
        herkunft=_vok(erg.herkunft),
        # „angenommen" steht schon als Herkunft — dasselbe Wort als Badge daneben
        # wäre die zweite Zeile für dieselbe Aussage (Team-Rückfrage 25 Aug).
        badge=_vok(erg.badge) if not (
            erg.badge == Badge.ANGENOMMEN and erg.herkunft == Herkunft.ANGENOMMEN
        ) else None,
        grund=_zurueck(erg.grund, fall.pseudonyme),
        zitate=[_zitat(q, fall.pseudonyme) for q in erg.zitate],
        anker=_anker(erg.anker, schema, erg.pruefpunkt_id),
        verwendet=_verwendet(erg, fall, k, schema),
        fehlt=erg.missing, owner=_vok(erg.owner),
        wertungsfrage=erg.wertungsfrage, llm_befund=erg.llm_befund,
        geprueft_von=[
            vm.Fachpruefung(wer=f.wer, am=f.am, beleg=f.beleg, umfang=f.umfang,
                            vorbehalt=f.vorbehalt)
            for f in (pp.geprueft_von if pp else [])
        ],
        frist=vm.Frist(**erg.frist.model_dump(exclude={"stand"}), stand=erg.frist.stand or "")
        if erg.frist else None,
        betrag=vm.Betrag(name=erg.betrag.name, wert=erg.betrag.wert, annahmen=erg.betrag.annahmen)
        if erg.betrag else None,
        inaktiv_grund=erg.inaktiv_grund,
        hinweis_abmahnung=_hinweis_abmahnung(erg, schema),
        normrang=_normrang(pp),
    )


# K58 — was in einer Norm-Pille steht.
#
# `kurzwort` ist die **amtliche Überschrift**, wörtlich und nur hinten gekürzt —
# nichts Eigenes. Alle Überschriften unten sind am 25.08.2026 gegen
# gesetze-im-internet.de geprüft; die Nummern der §§ 308/309 tragen dort eigene
# Klammerüberschriften („5. (Fingierte Erklärungen)"), die Nummern von § 309
# Nr. 9 **nicht** — dort steht deshalb der Titel.
#
# Wo dieselbe Überschrift zwei Punkte träfe (§ 307 dreimal „Inhaltskontrolle",
# § 308 Nr. 5 zweimal), steht das unterscheidende Wort aus dem Prüfpunkt-Titel
# in Klammern dahinter. `kurzwort_quelle` sagt, woher das Wort kommt:
# „amtlich" = Gesetzesüberschrift, „titel" = unser Prüfpunkt-Titel.
#
# Die Tabelle steht hier und nur hier (ONE source); ein Schema-Edit fasst sie
# nicht an. Franz nickt sie am 26. ab — seine Änderungen sind dann Daten.
# Schlüssel ist der **Anker**, nicht der Prüfpunkt: `ansicht.py` darf keinen
# Prüfpunkt beim Namen kennen (Test `test_evaluator_kennt_keinen_einzigen_
# pruefpunkt` hält das für die ganze Projektionsschicht). Damit gilt die
# Tabelle auch für Inkasso und überlebt jede Umbenennung im Schema.
KURZWORT: dict[str, tuple[str, str]] = {
    "bgb_310_3":   ("Anwendungsbereich", "amtlich"),
    "bgb_305_2":   ("Einbeziehung Allgemeiner Geschäftsbedingungen", "amtlich"),
    "bgb_305b":    ("Vorrang der Individualabrede", "amtlich"),
    "bgb_305c":    ("Überraschende und mehrdeutige Klauseln", "amtlich"),
    "bgb_306":     ("Rechtsfolgen bei Nichteinbeziehung", "amtlich"),   # „…und Unwirksamkeit"
    "bgb_307_1_1": ("Inhaltskontrolle (Symmetrie)", "amtlich"),
    "bgb_307_1_2": ("Inhaltskontrolle (Transparenz)", "amtlich"),
    "bgb_307_3":   ("Inhaltskontrolle (Kontrollfähigkeit)", "amtlich"),
    "bgb_308_4":   ("Änderungsvorbehalt", "amtlich"),
    "bgb_308_5":   ("Fingierte Erklärungen", "amtlich"),
    "bgb_309_13":  ("Form von Anzeigen und Erklärungen", "amtlich"),
    "bgb_315_3":   ("Bestimmung der Leistung", "amtlich"),              # „…durch eine Partei"
}

_ROEMISCH = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}


_GESETZ = re.compile(r"\s+([A-ZÄÖÜ][A-Za-zÄÖÜ]{1,9})\s*$")


def _norm_kurz(norm: str | None) -> str | None:
    """Die Fundstelle in juristischer Kurzform, **mit** dem Gesetz: ohne
    Klammerzusatz, bei mehreren zitierten Stellen nur die erste, „Abs. 1" → „I",
    „S. 2" → „2", „lit. b" → „b". Gekürzt und in die übliche Schreibweise
    gebracht, nicht umgedeutet: „§ 307 Abs. 1 S. 2 BGB" → „§ 307 I 2 BGB".

    Das Gesetz stand hier bis zum 26.08.2026 nicht dabei — innerhalb eines
    Schirms, auf dem ohnehin nur BGB zitiert wird, ist „§ 307 I 2" die übliche
    Schreibweise. Die Auftraggeberin hat darum gebeten, es überall dazuzuschreiben, und
    die Bitte trägt weiter als der Anlass: `schemas/inkasso.json` zitiert
    § 13a und § 13e RDG. Sobald eine zweite Fallgruppe auf demselben Schirm
    steht, ist „§ 13a" keine Fundstelle mehr, sondern eine Zahl.

    Rechtsprechung trägt kein Gesetz („BGH VIII ZR 138/07", „13 O 730/22") und
    wird deshalb nicht angefasst — erkennbar daran, dass kein „§" vorkommt."""
    if not norm:
        return None
    text = norm.split("(")[0].strip()
    gesetz = ""
    if "§" in text:
        treffer = _GESETZ.search(text)
        if treffer:
            gesetz = treffer.group(1)
            text = text[: treffer.start()]
    text = text.split(",")[0].strip()
    text = re.sub(r"Abs\.\s*(\d)", lambda m: _ROEMISCH.get(m.group(1), m.group(1)), text)
    text = re.sub(r"S\.\s*(\d)", r"\1", text)
    text = re.sub(r"lit\.\s*([a-z])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    return f"{text} {gesetz}" if gesetz else text


def _kurztitel(pp) -> str | None:
    if pp is None:
        return None
    return pp.titel.split("(")[0].strip().rstrip(":") or None


def _norm_und_kurzwort(pp, schema: Schema) -> tuple[str | None, str | None, str | None]:
    if pp is None:
        return None, None, None
    anker = (pp.anker or [None])[0]
    norm = _norm_kurz(anker.get("norm")) if anker else None
    key = anker.get("key") if anker else None
    # Tragen zwei Punkte dieselbe Norm (§ 308 Nr. 5 an zwei Stellen), sagt die
    # Überschrift nichts über den Unterschied — dann spricht unser Titel, und
    # `kurzwort_quelle` sagt genau das.
    geteilt = key is not None and sum(
        1 for anderer in schema.pruefpunkte
        if anderer.anker and (anderer.anker[0] or {}).get("key") == key
    ) > 1
    eintrag = KURZWORT.get(key or "")
    if eintrag and not geteilt:
        return norm, eintrag[0], eintrag[1]
    return norm, _kurztitel(pp), "titel"


# Anleitung §2 — Rangfolge § 309 > § 308 > § 307 > alles andere. Gelesen aus den
# Anker-Schlüsseln des Prüfpunkts (`bgb_309_13`, `bgb_308_5`, `bgb_307_1_2` …),
# nicht aus einem zweiten Feld, das jemand pflegen müsste.
_NORM_RANG = {"309": 0, "308": 1, "307": 2}


def _paragraf(pp) -> str | None:
    """Der höchstrangige BGB-Paragraf unter den Ankern eines Prüfpunkts."""
    beste = None
    for a in (pp.anker if pp else []):
        m = re.match(r"bgb_(\d{3})(?:_|$)", a.get("key") or "")
        if m and m.group(1) in _NORM_RANG:
            if beste is None or _NORM_RANG[m.group(1)] < _NORM_RANG[beste]:
                beste = m.group(1)
    return beste


def _normrang(pp) -> vm.Vokabel | None:
    return vm.Vokabel.von(Normrang.WERTUNGSFREI) if _paragraf(pp) in ("309", "308") else None


def _rangfolge(eintraege: list[vm.TraceEintrag], schema: Schema) -> list[vm.TraceEintrag]:
    """Innerhalb einer Stufe: NEIN-Zeilen zuerst, darunter § 309 vor § 308 vor
    § 307 vor Rest, tragend vor ergänzend; alles andere behält die Reihenfolge
    der Schemadatei. Die Stufen selbst bleiben, wie das Schema sie ordnet — die
    Einbeziehung (S2) steht dort schon vor der Inhaltskontrolle (S3), getrennt,
    wie §2 es verlangt. Nur Anzeige: `einordnung`, `gerissene_stufe` und der
    Brief werden von dieser Funktion nicht berührt (Test hält es fest)."""
    def schluessel(i_e):
        i, e = i_e
        nein = 0 if e.zustand.code == Zustand.NEIN.value else 1
        rang = _NORM_RANG.get(_paragraf(schema.pruefpunkt(e.pruefpunkt_id)) or "", 3)
        tragend = 0 if e.rolle.code == Rolle.TRAGEND.value else 1
        return (nein, rang, tragend, i) if nein == 0 else (nein, i)
    return [e for _, e in sorted(enumerate(eintraege), key=schluessel)]


def _hinweis_abmahnung(erg, schema: Schema) -> vm.AbmahnungHinweis | None:
    """Anleitung §7. Der Hinweis hängt am Prüfpunkt, nicht am Anbieter: er sagt
    „diese Klausel ist bekannt", nie „dieses Unternehmen wurde abgemahnt" — den
    Namen des Vorverfahrens-Verwenders trägt der Satz bewusst nicht."""
    if erg.zustand != Zustand.NEIN:
        return None
    from fallpruefer import abmahnungen
    from fallpruefer.vokabular import Radarhinweis

    hits = abmahnungen.fuer_pruefpunkt(schema.fallgruppe_id, erg.pruefpunkt_id)
    if not hits:
        return None
    a = hits[0]
    return vm.AbmahnungHinweis(
        badge=vm.Vokabel.von(Radarhinweis.BEREITS_ABGEMAHNT),
        text=a.satz(), geprueft=a.geprueft, quelle_url=a.quelle,
    )


def _stufen_anzeigezustand(eintraege: list[vm.TraceEintrag], op: str) -> Zustand:
    """Der Zustand, den die **Stufenzeile zeigt** — nicht der, mit dem das Urteil rechnet.

    `evaluator._knoten_zustand` aggregiert bewusst nur ueber `schema.nur_rolle`
    (Vorgabe `["tragend"]`), weil nur tragende Punkte die Einordnung bewegen. Fuer
    die Anzeige ist genau das falsch: eine Stufe, deren Punkte alle `gate` oder
    `ergaenzend` sind, hatte danach kein einziges aktives Kind und fiel auf
    INAKTIV — und INAKTIV heisst auf dem Schirm „nicht geprueft". Stufe 0
    behauptete so in *jedem* Fall, der Anwendungsbereich sei ungeprueft, waehrend
    P0 daneben mit verifiziertem Zitat auf „erfuellt" stand. Gefunden hat es das
    Team am 26. Aug mit der Frage „Warum ist diese Stufe in grau?" (`39` §A).

    Deshalb hier dieselbe Praezedenz wie im Evaluator, aber ueber **alle** Punkte
    der Stufe. Zwei Eigenschaften, auf die es ankommt:

    - Echte INAKTIV-Punkte bleiben uebersprungen, und eine Stufe, in der *jeder*
      Punkt inaktiv ist, bleibt INAKTIV. Das Wort „nicht geprueft" verschwindet
      nicht — es gilt nur noch dort, wo es stimmt (P1a-Pfad, siehe
      `tests/test_fall6_existiert_nicht.py`). Vorher war Stufe 0 in jedem Fall
      grau und sagte damit nichts; jetzt ist sie es nur, wenn wirklich nichts
      geprueft wurde.
    - Das Urteil bleibt unberuehrt: `wurzel` und `gerissene_stufe` lesen weiter
      `pruefung.baum_zustaende`, also weiter nur ueber tragende Punkte.
    """
    aktive = {e.zustand.code for e in eintraege
              if e.zustand is not None and e.zustand.code != Zustand.INAKTIV.value}
    if not aktive:
        return Zustand.INAKTIV
    praezedenz = ((Zustand.JA, Zustand.WERTUNG, Zustand.FEHLT, Zustand.NEIN)
                  if op.upper() == "OR"
                  else (Zustand.NEIN, Zustand.FEHLT, Zustand.WERTUNG, Zustand.JA))
    return next((z for z in praezedenz if z.value in aktive), Zustand.INAKTIV)


def _stufe_titel(schema: Schema, stufe_id: str | None) -> str | None:
    """Das Wort zur Kennung: `S2` → „Stufe 2 — Einbeziehung".

    `gerissene_stufe` **bleibt die Kennung** — sie ist eine Identität, keine
    Beschriftung: drei Wächter halten sie gegen den Motor (`test_pruefbaum`
    vergleicht sie sogar mit `knoten_id`), die Rechtsbehelf-Regeln lesen sie als
    Menge `S1,S2,S3`, und die Goldens prüfen sie. Das Wort kommt deshalb
    **daneben**, nicht statt ihrer.

    Warum es überhaupt der Motor tut: die Anzeigeseite mappt nie einen Code auf
    einen String (`27` §2), sie darf also aus `S2` nicht selbst „Stufe 2" machen.
    Quelle ist dieselbe wie für `stufen[].titel`. Kein Prüfschema (Stufe C) oder
    eine unbekannte Stufe → die Kennung bleibt lesbar stehen.
    """
    if not stufe_id:
        return None
    baum = getattr(schema, "baum", None)
    for kind in getattr(baum, "kinder", None) or []:
        if getattr(kind, "id", None) == stufe_id:
            return kind.titel or stufe_id
    return stufe_id


def _pruefpfad(pruefung: Pruefung, fall: Fall, schema: Schema, k: Fallkontext) -> vm.Pruefpfad:
    nach_id = {e.pruefpunkt_id: e for e in pruefung.ergebnisse}
    stufen: list[vm.StufenEintrag] = []
    zugeordnet: set[str] = set()

    for kind in (schema.baum.kinder if schema.baum else []):
        if not isinstance(kind, Knoten):
            continue
        eintraege = []
        for pid in kind.kinder:
            if isinstance(pid, str) and pid in nach_id:
                eintraege.append(_trace(nach_id[pid], fall, schema, k))
                zugeordnet.add(pid)
        stufen.append(vm.StufenEintrag(
            stufe_id=kind.id, titel=kind.titel,
            zustand=_vok(_stufen_anzeigezustand(eintraege, kind.op)),
            pruefpunkte=_rangfolge(eintraege, schema),
        ))

    ableitungen = [
        _trace(e, fall, schema, k) for e in pruefung.ergebnisse
        if e.pruefpunkt_id not in zugeordnet
    ]
    baum = _baum(pruefung, stufen, schema)
    return vm.Pruefpfad(
        wurzel=_vok(pruefung.baum_zustaende.get("root", Zustand.INAKTIV)),
        gerissene_stufe=pruefung.gerissene_stufe,
        gerissene_stufe_titel=_stufe_titel(schema, pruefung.gerissene_stufe),
        stufen=stufen, ableitungen=ableitungen,
        baum=baum, legende=_legende(baum),
    )


def _legende(baum: vm.BaumKnoten | None) -> list[vm.Vokabel]:
    """Was im Baum steht und einen Satz hat — Rollen, Zustände, Marker, die
    Verknüpfung. Reihenfolge: Rolle vor Zustand vor Rest, `tragend` zuerst,
    weil es das einzige ist, das der Baum **nicht** als Abzeichen zeigt (K55)
    und das trotzdem erklärt gehört. Keine Vokabel ohne `detail`, kein Satz
    von hier."""
    if baum is None:
        return []
    from fallpruefer.vokabular import Rolle

    aus: list[vm.Vokabel] = []
    gesehen: set[str] = set()

    def hinzu(v: vm.Vokabel | None) -> None:
        if v is None or not v.detail or v.code in gesehen:
            return
        gesehen.add(v.code)
        aus.append(v)

    # `tragend` steht in keinem Knoten mehr — die Vokabel kommt aus derselben
    # Quelle wie jede andere, nur ohne Umweg über einen Chip.
    if any(k.rolle and k.rolle.code == Rolle.TRAGEND.value
           for k in _flach(baum)):
        hinzu(vm.Vokabel.von(Rolle.TRAGEND))
    for k in _flach(baum):
        hinzu(k.rolle)
    for k in _flach(baum):
        hinzu(k.zustand)
        hinzu(k.marker)
        hinzu(k.op)
    return aus


def _flach(k: vm.BaumKnoten) -> list[vm.BaumKnoten]:
    return [k] + [x for c in k.kinder for x in _flach(c)]


def _baum(pruefung: Pruefung, stufen: list[vm.StufenEintrag], schema: Schema) -> vm.BaumKnoten | None:
    """R7: Schema-Baum + Zustände der Prüfung → Anzeige-Baum. Keine zweite
    Bewertung: Stufenzustand ist `StufenEintrag.zustand`, Punktzustand der
    der Detailzeile, Wurzel `baum_zustaende["root"]`. `inaktiv_durch` wird
    aus dem Schema abgelesen — welcher NEIN-Punkt diesen Knoten per
    `bei_NEIN.deaktiviert` abgeschaltet hat."""
    from fallpruefer.vokabular import Baummarker, Verknuepfung

    if not schema.baum:
        return None
    zeilen = {p.pruefpunkt_id: p for s in stufen for p in s.pruefpunkte}
    abgeschaltet: dict[str, str] = {}
    for pp in schema.pruefpunkte:
        z = zeilen.get(pp.id)
        if z is not None and z.zustand.code == Zustand.NEIN.value and pp.bei_NEIN:
            for pid in pp.bei_NEIN.get("deaktiviert", []):
                abgeschaltet.setdefault(pid, pp.titel)

    def op_vok(op: str) -> vm.Vokabel | None:
        try:
            return vm.Vokabel.von(Verknuepfung(op))
        except ValueError:
            return None

    def punkt(pid: str, stufe_gerissen: bool) -> vm.BaumKnoten | None:
        z = zeilen.get(pid)
        if z is None:
            return None
        ist_nein = z.zustand.code == Zustand.NEIN.value
        norm, wort, quelle = _norm_und_kurzwort(schema.pruefpunkt(pid), schema)
        return vm.BaumKnoten(
            knoten_id=pid, art=vm.Vokabel.von(Baummarker.PRUEFPUNKT), titel=z.titel,
            norm_kurz=norm, kurzwort=wort, kurzwort_quelle=quelle,
            zustand=z.zustand, rolle=z.rolle,
            gerissen=stufe_gerissen and ist_nein,
            marker=vm.Vokabel.von(Baummarker.GERISSEN) if stufe_gerissen and ist_nein else None,
            inaktiv_durch=abgeschaltet.get(pid) if z.zustand.code == Zustand.INAKTIV.value else None,
        )

    kinder: list[vm.BaumKnoten] = []
    for kind in schema.baum.kinder:
        if not isinstance(kind, Knoten):
            continue
        eintrag = next((s for s in stufen if s.stufe_id == kind.id), None)
        if eintrag is None:
            continue
        gerissen = pruefung.gerissene_stufe == kind.id
        # Reihenfolge wie in der Detailliste (1.7 Rangfolge § 309 > § 308 > § 307),
        # damit Baumzeile und aufgeklappte Zeile dieselbe Reihenfolge haben.
        punkte = [k for k in (punkt(z.pruefpunkt_id, gerissen) for z in eintrag.pruefpunkte) if k]
        alle_inaktiv = bool(punkte) and all(k.zustand.code == Zustand.INAKTIV.value for k in punkte)
        kinder.append(vm.BaumKnoten(
            knoten_id=kind.id, art=vm.Vokabel.von(Baummarker.STUFE), titel=kind.titel,
            op=op_vok(kind.op), zustand=eintrag.zustand, gerissen=gerissen,
            marker=vm.Vokabel.von(Baummarker.GERISSEN) if gerissen else None,
            inaktiv_durch=next((k.inaktiv_durch for k in punkte if k.inaktiv_durch), None)
            if alle_inaktiv else None,
            anzahl_pruefpunkte=len(punkte), kinder=punkte,
        ))
    return vm.BaumKnoten(
        knoten_id=schema.baum.id, art=vm.Vokabel.von(Baummarker.WURZEL),
        titel=schema.baum.titel or "Gesamtergebnis",
        op=op_vok(schema.baum.op),
        zustand=_vok(pruefung.baum_zustaende.get("root", Zustand.INAKTIV)),
        anzahl_pruefpunkte=sum(k.anzahl_pruefpunkte for k in kinder), kinder=kinder,
    )


def _feldname(feld_id: str, schema: Schema) -> str:
    spec = schema.dokumenten_soll.feld(feld_id)
    if spec and spec.label:
        return spec.label
    if spec and spec.beschreibung:
        return spec.beschreibung
    return feld_id.split(".", 1)[-1] if "." in feld_id else feld_id


def _posten(el, schema: Schema) -> vm.VollstaendigkeitsPosten:
    sd = schema.dokumenten_soll.nach_typ(el.dokumenttyp) if el.dokumenttyp else None
    return vm.VollstaendigkeitsPosten(
        was=sd.anzeigename if sd else (el.grund or el.feld_id or ""),
        grund=(sd.begruendung_satz if sd else el.grund) or "",
        quelle=_vok(el.quelle),
        dokumenttyp=_vok(el.dokumenttyp),
        feld_id=el.feld_id, pruefpunkt_id=el.pruefpunkt_id,
        beschaffungsweg=sd.beschaffungsweg if sd else None,
        fehlzustand=_vok(el.fehlzustand) if el.fehlzustand else None,
        aussage=el.aussage,
    )


def _posten_gruppiert(eintraege, schema: Schema) -> list[vm.VollstaendigkeitsPosten]:
    """One row per document — the rule the verdict (18 #29) and the
    Nachforderung letter (18 #28) already follow, applied to the projection too.

    Without it the panel asked for the same AGB once per unfound field: seven
    identical rows next to a letter that, correctly, asked once. A document
    that never arrived is named by itself; a document on file with several
    fields unfound is „… (unvollständig)"; a single missing field is named as
    itself, so „die Seite mit Ziffer 5.2" does not get blurred into „die AGB".
    """
    gruppen: dict[str, list] = {}
    einzeln: list = []
    for el in eintraege:
        if el.dokumenttyp:
            gruppen.setdefault(el.dokumenttyp.value, []).append(el)
        else:
            einzeln.append(el)

    aus: list[vm.VollstaendigkeitsPosten] = []
    for gruppe in gruppen.values():
        felder = [_feldname(e.feld_id, schema) for e in gruppe if e.feld_id]
        dokument_fehlt = any(e.feld_id is None for e in gruppe)
        kopf = next((e for e in gruppe if e.feld_id is None), gruppe[0])
        p = _posten(kopf, schema)
        if dokument_fehlt:
            p.feld_id = None
        elif len(gruppe) > 1:
            p.was = (f"{p.was} — liegen vor, aber unvollständig" if str(p.was).strip().lower().startswith("die agb") else f"{p.was} — liegt vor, aber unvollständig")
            p.feld_id = None
        else:
            p.was = felder[0] if felder else p.was
        p.felder = felder
        aus.append(p)
    for el in einzeln:
        aus.append(_posten(el, schema))
    return aus


def _hero(pruefung: Pruefung, schema: Schema) -> vm.Hero:
    code = pruefung.einordnung_code or Einordnung.UNKLAR
    voll = pruefung.vollstaendigkeit
    verbraucher = _posten_gruppiert(voll.get("verbraucher", []), schema)
    unternehmen = _posten_gruppiert(voll.get("unternehmen", []), schema)

    umfang: list[vm.PruefumfangEintrag] = []
    for pid in pruefung.pruefumfang:
        pp = schema.pruefpunkt(pid)
        erg = pruefung.ergebnis(pid)
        if not pp or not erg:
            continue
        umfang.append(vm.PruefumfangEintrag(
            pruefpunkt_id=pid, titel=pp.titel, zustand=_vok(erg.zustand),
            text=pp.pruefumfang_text or erg.wertungsfrage or erg.inaktiv_grund or erg.grund,
        ))

    # A Stufe-B/C Fallgruppe produces no verdict at all (evaluator._einordnung).
    # The hero then carries the limitation sentence rather than an empty Ampel —
    # „the user-facing sentence states a program limitation, never a
    # Zuständigkeit judgment" (14 §2).
    text = pruefung.einordnung or konfig().texte.get(
        f"stufe_{schema.stufe.value.lower()}_hinweis", ""
    )

    return vm.Hero(
        einordnung=vm.EinordnungAnsicht(
            code=code.value if pruefung.einordnung_code else "keine_pruefung",
            label=text,
            label_basis=label(code) if pruefung.einordnung_code else "keine Prüfung hinterlegt",
            tone=ton(code) if pruefung.einordnung_code else "grau",
        ),
        vollstaendigkeit=vm.Vollstaendigkeit(
            verbraucher=verbraucher, unternehmen=unternehmen,
            vollstaendig_verbraucherseite=not verbraucher,
        ),
        plain=pruefung.plain,
        pruefumfang=umfang,
    )


def _offene_punkte(
    pruefung: Pruefung, schema: Schema, beantwortet: frozenset[str] = frozenset()
) -> list[vm.OffenerPunkt]:
    """14 §6: consumer-side FEHLT + WERTUNG questions + Leitfaden questions of
    the Prüfpunkte that are actually open. Company-side gaps belong in
    Vollständigkeit, not here — they are not something to ask the consumer.

    `beantwortet` are the Prüfpunkte whose Leitfaden question the advisor has
    already answered (or that fell away). A question that was answered a
    minute ago and still stands under „Offene Punkte" reads as „the program
    forgot" (28 F8) — the WERTUNG entry of the same Prüfpunkt stays, because
    that is the advisor's judgment, not the consumer's answer."""
    aus: list[vm.OffenerPunkt] = []
    for p in _posten_gruppiert(pruefung.vollstaendigkeit.get("verbraucher", []), schema):
        aus.append(vm.OffenerPunkt(
            art=_vok(OffenerPunktArt.FEHLT), text=p.was or p.grund,
            pruefpunkt_id=p.pruefpunkt_id, quelle=p.quelle, feld_id=p.feld_id,
            pruefpunkt_titel=_titel_im_schema(schema, p.pruefpunkt_id),
            feld_label=_feld_label_im_schema(schema, p.feld_id),
        ))
    for erg in pruefung.ergebnisse:
        pp = schema.pruefpunkt(erg.pruefpunkt_id)
        if not pp or erg.zustand != Zustand.WERTUNG:
            continue
        if erg.wertungsfrage:
            aus.append(vm.OffenerPunkt(
                art=_vok(OffenerPunktArt.WERTUNG), text=erg.wertungsfrage,
                pruefpunkt_id=erg.pruefpunkt_id, pruefpunkt_titel=pp.titel,
            ))
        if erg.pruefpunkt_id in beantwortet:
            continue
        if pp.leitfaden_frage and pp.leitfaden_frage.get("text"):
            aus.append(vm.OffenerPunkt(
                art=_vok(OffenerPunktArt.FRAGE), text=pp.leitfaden_frage["text"],
                pruefpunkt_id=erg.pruefpunkt_id, pruefpunkt_titel=pp.titel,
            ))
    return aus


def _musterbrief(fall: Fall, schema: Schema) -> vm.Musterbrief | None:
    r = fall.rechtsbehelf
    if not r.brief:
        return None
    from fallpruefer.vokabular import Briefquelle

    vorschlaege = []
    for rid in r.vorschlaege:
        rb = schema.rechtsbehelfe.nach_id(rid)
        if rb:
            vorschlaege.append(vm.RechtsbehelfsVorschlag(
                rechtsbehelf_id=rid, titel=rb.titel,
                hauptvorschlag=(rid == r.hauptvorschlag), geprueft=rb.geprueft,
            ))
    gewaehlt = schema.rechtsbehelfe.nach_id(r.gewaehlt or "")
    return vm.Musterbrief(
        rechtsbehelf_id=r.gewaehlt or "", titel=gewaehlt.titel if gewaehlt else r.brief.titel,
        text=r.brief.text, status=_vok(r.brief.status), template_id=r.brief.template_id,
        variante=r.brief.variante, quelle=_vok(Briefquelle(r.brief.quelle)),
        quelle_url=r.brief.quelle_url, empfaenger=_vok(r.brief.empfaenger),
        platzhalter=r.brief.platzhalter, geprueft=r.brief.geprueft,
        vorschlaege=vorschlaege,
    )


def _nachforderungen(fall: Fall) -> list[vm.NachforderungAnsicht]:
    return [
        vm.NachforderungAnsicht(
            id=n.id, kanal=_vok(n.kanal),
            dokumente=[_vok(d) for d in n.dokumente],
            # the advisor reads this, so the tokens come back out here — one of
            # the exactly two places re-identification happens (contract §4)
            text=_zurueck(n.text, fall.pseudonyme),
            status=_vok(n.status), zeit=n.zeit,
        )
        for n in fall.nachforderungen
    ]


def _laeufe(fall: Fall, schema: Schema) -> list[vm.LaufAnsicht]:
    from fallpruefer.vokabular import ton

    aus: list[vm.LaufAnsicht] = []
    for p in fall.pruefungen:
        code = p.einordnung_code or Einordnung.UNKLAR
        gate3 = p.gate3 or {}
        try:
            trigger = _vok(Lauftrigger(p.trigger))
        except ValueError:
            # a trigger the vocabulary does not know yet — readable beats red
            trigger = Vokabel(code=p.trigger, label=p.trigger, tone="grau")
        aus.append(vm.LaufAnsicht(
            run_id=p.run_id, trigger=trigger, zeit=p.zeit,
            einordnung=p.einordnung, einordnung_tone=ton(code),
            gerissene_stufe=p.gerissene_stufe,
            gerissene_stufe_titel=_stufe_titel(schema, p.gerissene_stufe), aktuell=p.aktuell,
            gate3_bestaetigt=gate3.get("aktion") == "bestaetigt",
            gate3_gueltig=bool(gate3.get("gueltig", True)),
        ))
    return aus


def _referat(fall: Fall, pruefung: Pruefung, k: Fallkontext, schema: Schema) -> vm.ReferatPanel:
    c = konfig()
    evidenz: dict[str, str] = {}
    alt = k.feld("erhoehungsschreiben.alter_betrag")
    neu = k.feld("erhoehungsschreiben.neuer_betrag")
    if alt is not None and neu is not None:
        evidenz["schadenshoehe"] = f"Erhöhung {zeit.betrag_de(float(neu) - float(alt))} im Monat"

    # „Dauerbrenner" is one of the six published FWN criteria (`10` §5) and the
    # one an advisor cannot judge from the case in front of them — it is a
    # statement about the corpus. The store has known it all along; the panel
    # asked for the tick without ever showing the evidence.
    #
    # `anbieter_bestand` carries the k_min threshold, so it is not re-checked
    # here: below it the object says nothing, and nothing is exactly what is
    # rendered — no counter, no placeholder, no greyed-out row. „Suppressed"
    # and „no such Anbieter" have to look the same from outside (`store.py`),
    # which is why this is an `if` around the assignment and not around a text.
    from fallpruefer import store

    bestand = store.anbieter_bestand(fall.eingang.anbieter, fall.schema_.fallgruppe_id)
    if bestand.ausgewiesen:
        satz = f"{bestand.faelle} Fälle zu diesem Anbieter im Bestand"
        # Prüfpunkt-Nummern gehören nicht auf einen Schirm, den ein Mensch
        # liest — die Einordnung nennt aus demselben Grund keine (ein Test in
        # `evaluator` hält das fest), und gegenüber dem Team gilt dieselbe
        # Regel. „P6 (3×)" sagt einer Beraterin nichts; der Titel sagt ihr,
        # woran die Fälle dieses Anbieters reihum brechen.
        wiederkehrend = []
        for pid, n in bestand.gleicher_pruefpunkt.items():
            if n < 2:
                continue
            pp = schema.pruefpunkt(pid)
            wiederkehrend.append(f"{pp.titel if pp else pid} ({n}×)")
        if wiederkehrend:
            satz += " · immer wieder: " + ", ".join(wiederkehrend)
        evidenz["dauerbrenner"] = satz

    kriterien = [
        vm.ReferatKriterium(
            id=kr["id"], label=kr["label"],
            angehakt=kr["id"] in fall.referat_markierung.kriterien,
            evidenz=evidenz.get(kr["id"]),
        )
        for kr in c.referat_kriterien
    ]
    return vm.ReferatPanel(
        kriterien=kriterien, notiz=fall.referat_markierung.notiz,
        markiert=bool(fall.referat_markierung.kriterien),
        hinweis=c.referat_hinweis,
    )


def _fusszeile(fall: Fall, pruefung: Pruefung, schema: Schema) -> vm.Fusszeile:
    bestaetigt, gesamt = schema.fachpruefung_stand()
    c = konfig()
    return vm.Fusszeile(
        disclaimer=c.texte.get("disclaimer", ""),
        ki_hinweis=c.texte.get("ki_hinweis", ""),
        # the version that produced *this* verdict, not the file as it stands
        # now: during the Akt-2 window the two differ, and a footer naming a
        # version that did not decide the case above it is the wrong way round
        schema_version=pruefung.schema_version or schema.version,
        schema_stand=pruefung.schema_stand or schema.stand,
        stand=zeit.heute().isoformat(),
        stichtag=zeit.heute().isoformat(), stichtag_modus=c.stichtag_modus,
        betriebskosten_cent=round(sum(r.kosten_cent for r in fall.llm_runs), 2),
        normbasis_modus=c.normbasis_modus,
        # Wie viele Prüfpunkte fachlich bestätigt sind, als Zahl statt als
        # dreizehn Negativabzeichen. Ohne sie läse sich der Schirm falsch
        # herum: eine unbestätigte *Fundstelle* trägt sichtbar „ungeprüft",
        # eine unbestätigte *Bewertung* wäre stumm — markiert wäre dann die
        # falsche Hälfte. Der Satz dazu steht in der Anzeige, nicht im Motor.
        fachpruefung_bestaetigt=bestaetigt, fachpruefung_gesamt=gesamt,
    )



def _lbl(enum_klasse, wert) -> str:
    """A detail value that is really an enum code — shown as its label.

    The log is a surface like any other: contract §0 forbids the UI from
    mapping a code to a string, so „agb" must leave the backend as
    „AGB / Vertragsbedingungen". Unknown values pass through unchanged rather
    than raising — a log line is not worth a 500.
    """
    try:
        return label(enum_klasse(wert))
    except (ValueError, KeyError):
        return str(wert)


def _lbls(enum_klasse, werte) -> str:
    return ", ".join(_lbl(enum_klasse, w) for w in (werte or []))

# --------------------------------------------------------------------------
# the event log (contract §12) — ABBYY's Ereignisprotokoll, our workflow
# --------------------------------------------------------------------------

# What a log line says in words. One entry per action; the value is a callable
# over the event's details, so nothing from `details` reaches the screen that
# was not deliberately put there. Actions whose details add nothing map to "".
#
# This is a whitelist on purpose: `details` is an open dict, it can hold an
# exception message (`brief_nicht_erzeugt`) or advisor free text
# (`gate3_override.grund`), and dumping it raw would ship pseudonym tokens and
# stack noise onto the advisor's screen.
_PROTOKOLL_TEXT: dict[Protokollaktion, Any] = {
    Protokollaktion.L0_PSEUDONYMISIERT:
        lambda d: f"{d.get('tokens', 0)} Identitätsangaben ersetzt",
    Protokollaktion.DOKUMENT_KLASSIFIZIERT:
        lambda d: f"{d.get('dok_id', '?')} \u2192 {_lbl(Dokumenttyp, d.get('typ'))}",
    Protokollaktion.EXTRAKTION_VERWORFEN:
        lambda d: "Felder: " + ", ".join(d.get("felder", [])),
    Protokollaktion.FALLGRUPPE_VORSCHLAG_FEHLGESCHLAGEN:
        lambda d: str(d.get("grund", "")),
    Protokollaktion.GATE2_FALLGRUPPE_GEWAEHLT:
        lambda d: str(d.get("fallgruppe_id", ""))
        + (" (gewechselt)" if d.get("gewechselt") else ""),
    Protokollaktion.SCHEMA_GELADEN:
        lambda d: f"Version {d.get('version', '?')} · Stand {d.get('stand', '?')}",
    # Die run_id ist eine interne Laufmarke; das Wort steht in `trigger` und
    # sagt dasselbe, was die Verlaufszeile seit K60/K62 zeigt (eine Quelle).
    Protokollaktion.PRUEFUNG_GELAUFEN:
        lambda d: f"Auslöser: {d.get('trigger', '?')}",
    Protokollaktion.SCHEMA_STOPP: lambda d: str(d.get("text", "")),
    # V-N2 — Motor-Sitzung, Wortlaut zur Nacharbeit an die UI-Sitzung
    Protokollaktion.DOKUMENT_ALS_NICHT_VORHANDEN_MARKIERT:
        lambda d: f"{_lbl(Dokumenttyp, d.get('dokumenttyp'))}: "
        f"nach Angabe nicht vorhanden \u2014 \u201e{d.get('aussage', '')}\u201c",
    Protokollaktion.DOKUMENT_NICHT_VORHANDEN_ZURUECKGEZOGEN:
        lambda d: f"{_lbl(Dokumenttyp, d.get('dokumenttyp'))}: "
        f"Feststellung zur\u00fcckgenommen",
    Protokollaktion.GATE1_NACHFORDERUNG_ERZEUGT:
        lambda d: f"{_lbl(Kanal, d.get('kanal'))} · " + _lbls(Dokumenttyp, d.get("dokumente")),
    Protokollaktion.GATE1_NACHFORDERUNG_MARKIERT:
        lambda d: _lbl(Nachforderungsstatus, d.get("status")),
    Protokollaktion.NACHREICHUNG_EINGEGANGEN:
        lambda d: ", ".join(d.get("dokumente", [])),
    Protokollaktion.GATE3_OVERRIDE:
        lambda d: f"{d.get('pruefpunkt_id', '?')} \u2192 "
                  f"{_lbl(Zustand, d.get('neuer_zustand'))} · "
                  f"Grund: {d.get('grund', '')}",
    Protokollaktion.GATE3_OVERRIDE_ZURUECKGEZOGEN:
        lambda d: str(d.get("pruefpunkt_id", "")),
    Protokollaktion.GATE3_BESTAETIGT: lambda _d: "",
    Protokollaktion.GATE3_UNGUELTIG:
        lambda _d: "durch einen neuen Prüflauf überholt",
    Protokollaktion.LEITFADEN_ANTWORT:
        lambda d: f"{d.get('feld', '?')} = "
                  + ("keine Angabe" if d.get("wert") is None else str(d.get("wert")))
                  + (" · widerspricht einer Unterlage"
                     if d.get("widerspricht_unterlage") else ""),
    Protokollaktion.GATE4_RECHTSBEHELF_GEWAEHLT:
        lambda d: str(d.get("rechtsbehelf_id", "")),
    Protokollaktion.RECHTSBEHELF_ENTFAELLT: lambda d: str(d.get("grund", "")),
    Protokollaktion.BRIEF_ERZEUGT:
        lambda d: str(d.get("template", ""))
        + (" · " + "+".join(d["varianten"]) if d.get("varianten") else ""),
    Protokollaktion.BRIEF_NICHT_ERZEUGT:
        lambda d: f"{d.get('template', '?')}: {d.get('grund', '')}",
    Protokollaktion.BRIEF_STATUS:
        lambda d: f"{d.get('template', '?')} \u2192 {_lbl(Briefstatus, d.get('status'))}",
    Protokollaktion.REFERAT_MARKIERT:
        lambda d: ", ".join(d.get("kriterien", [])),
    # Der `fall_hash` ist der Anonymitätsschlüssel des Radars, kein Wort für
    # die Beraterin — und er stand als 32 Hexzeichen in ihrem Protokoll.
    Protokollaktion.STORE_GESCHRIEBEN: lambda _d: "anonymisiert für das Radar vermerkt",
    Protokollaktion.ABSCHLUSS_BASIS_EXPORT: lambda _d: "",
    Protokollaktion.FALL_GESCHLOSSEN: lambda _d: "",
}


# R6: `dokument.eingegangen` ist ein Code („eingang" / „nachreichung") und stand
# so im Dokument-Kopf auf dem Schirm — das erste Element links, in jedem Fall.
# Die Anzeige liefert den Satz; das UI mappt nichts (06 ⑧).
_EINGEGANGEN = {"eingang": "mit dem Ersteingang", "nachreichung": "nachgereicht"}


def _rechtsbehelf_titel(fall: Fall, rid: str | None) -> str:
    """R6: `musterbrief_kuendigung · sonderkuendigung` war die Protokollzeile —
    ids der Schemadatei vor der Beraterin. Der Titel steht im Schema; eine
    unbekannte id bleibt lesbar als sie selbst (alter Fall, gelöschter Eintrag)."""
    if not rid:
        return "?"
    try:
        from fallpruefer.schema import schema_laden

        r = schema_laden(fall.schema_.fallgruppe_id).rechtsbehelfe.nach_id(rid)
        return r.titel if r else rid
    except Exception:  # noqa: BLE001 — eine Protokollzeile darf die Akte nicht kippen
        return rid


def _template_titel(_fall: Fall, template: str | None) -> str:
    """R6: der Titel aus dem Vorlagenkopf statt der Datei-id („nachforderung_vbs")."""
    if not template:
        return "?"
    try:
        from fallpruefer.brief import vorlage_laden

        return vorlage_laden(template).titel
    except Exception:  # noqa: BLE001 — eine Protokollzeile darf die Akte nicht kippen
        return template


def _titel_im_schema(schema: Schema, pid: str | None) -> str | None:
    """Wie `_pruefpunkt_titel`, aber wo das Schema schon zur Hand ist."""
    pp = schema.pruefpunkt(pid) if pid else None
    return pp.titel if pp else None


def _feld_label_im_schema(schema: Schema, feld_id: str | None) -> str | None:
    spec = schema.dokumenten_soll.feld(feld_id) if feld_id else None
    return spec.label if spec and spec.label else None


def _pruefpunkt_titel(fall: Fall, pid: str | None) -> str:
    """Wie `_rechtsbehelf_titel`, fuer Prüfpunkte: `P6 → erfüllt` stand als
    Protokollzeile vor der Beraterin, obwohl der Evaluator eigens einen Test
    hat, dass er nie einen Prüfpunkt beim Namen nennt. Eine unbekannte id
    bleibt lesbar als sie selbst."""
    if not pid:
        return "?"
    try:
        from fallpruefer.schema import schema_laden

        pp = schema_laden(fall.schema_.fallgruppe_id).pruefpunkt(pid)
        return pp.titel if pp else pid
    except Exception:  # noqa: BLE001 — eine Protokollzeile darf die Akte nicht kippen
        return pid


def _feld_titel(fall: Fall, feld_id: str | None) -> str:
    """`gespraech.strategie = kuendigen` war die Protokollzeile — derselbe
    Befund, den H4 auf dem Leitfadenschirm geschlossen hat, eine Fläche
    weiter. Quelle ist dieselbe: die Beschriftung am Feld im Dokumenten-Soll."""
    if not feld_id:
        return "?"
    try:
        from fallpruefer.schema import schema_laden

        spec = schema_laden(fall.schema_.fallgruppe_id).dokumenten_soll.feld(feld_id)
        return spec.label if spec and spec.label else feld_id
    except Exception:  # noqa: BLE001
        return feld_id


def _protokoll(fall: Fall) -> list[vm.ProtokollEintrag]:
    eintraege: list[vm.ProtokollEintrag] = []
    kriterien_labels = {k["id"]: k["label"] for k in konfig().referat_kriterien}
    for e in fall.ereignisse:
        try:
            aktion = Protokollaktion(e.aktion)
        except ValueError:
            # A `protokoll()` call without a vocabulary entry. A test catches
            # this in the suite; on screen the log stays readable rather than
            # the whole Fallakte failing over one unlabelled line.
            eintraege.append(vm.ProtokollEintrag(
                zeit=e.zeit, akteur=e.akteur,
                aktion=Vokabel(code=e.aktion, label=e.aktion, tone="grau"),
            ))
            continue
        d = dict(e.details or {})
        # R6 — Codes, die bisher roh in der Beschreibung standen, als Wörter
        if aktion == Protokollaktion.PRUEFUNG_GELAUFEN:
            d["trigger"] = _lbl(Lauftrigger, d.get("trigger"))
        elif aktion == Protokollaktion.GATE2_FALLGRUPPE_GEWAEHLT:
            d["fallgruppe_id"] = _fallgruppe_vokabel(d.get("fallgruppe_id") or "").label
        elif aktion == Protokollaktion.GATE4_RECHTSBEHELF_GEWAEHLT:
            d["rechtsbehelf_id"] = _rechtsbehelf_titel(fall, d.get("rechtsbehelf_id"))
        elif aktion in (Protokollaktion.BRIEF_ERZEUGT, Protokollaktion.BRIEF_NICHT_ERZEUGT,
                        Protokollaktion.BRIEF_STATUS):
            d["template"] = _template_titel(fall, d.get("template"))
            # Varianten-ids sind Textbaustein-Schalter der Vorlage, keine Wörter
            # für die Beraterin — die Zahl sagt, was sie wissen muss.
            if d.get("varianten"):
                n = len(d["varianten"])
                d["varianten"] = [f"{n} Textbaustein{'' if n == 1 else 'e'}"]
        elif aktion == Protokollaktion.REFERAT_MARKIERT:
            d["kriterien"] = [kriterien_labels.get(c, c) for c in d.get("kriterien") or []]
        elif aktion in (Protokollaktion.GATE3_OVERRIDE,
                        Protokollaktion.GATE3_OVERRIDE_ZURUECKGEZOGEN):
            d["pruefpunkt_id"] = _pruefpunkt_titel(fall, d.get("pruefpunkt_id"))
        elif aktion == Protokollaktion.LEITFADEN_ANTWORT:
            d["feld"] = _feld_titel(fall, d.get("feld"))
        elif aktion == Protokollaktion.EXTRAKTION_VERWORFEN:
            d["felder"] = [_feld_titel(fall, f) for f in d.get("felder") or []]
        elif aktion == Protokollaktion.RECHTSBEHELF_ENTFAELLT and d.get("rechtsbehelf_id"):
            d["grund"] = f"{_rechtsbehelf_titel(fall, d.get('rechtsbehelf_id'))}: {d.get('grund', '')}"
        text = _PROTOKOLL_TEXT[aktion](d)
        eintraege.append(vm.ProtokollEintrag(
            zeit=e.zeit, akteur=e.akteur,
            aktion=_vok(aktion),
            schritt=_vok(PROTOKOLL_SCHRITT[aktion]),
            beschreibung=_zurueck(text, fall.pseudonyme),
        ))
    return eintraege



def _anker_roh(roh: list[dict]) -> list[vm.Anker]:
    """Anchors as a Beratungshinweis carries them — the raw schema dicts, not
    Prüfpunkt-resolved keys. Same resolver, same rendering, same `geprueft`
    semantics as everywhere else; H3 deliberately has none (its two norms hang
    on facts we do not extract, and an anchor would claim otherwise)."""
    nb = normbasis()
    aus: list[vm.Anker] = []
    for a in roh:
        key = a.get("key")
        if not key:
            continue
        e = nb.aufloesen(key, a)
        aus.append(vm.Anker(
            key=e.key, label=e.label, ebene=_vok(e.ebene), status=_vok(e.status),
            geprueft=e.geprueft, aufgeloest=e.aufgeloest, kernaussage=e.kernaussage,
            text=e.text, url=e.url, stand=e.stand,
            pruefstand=_vok(
                Ankerpruefstand.GEPRUEFT if e.geprueft else Ankerpruefstand.UNGEPRUEFT
            ),
        ))
    return aus


def _beratungshinweise(pruefung: Pruefung, fall: Fall, schema: Schema) -> list[vm.BeratungshinweisAnsicht]:
    """The run carries only the IDs (like `pruefumfang`); the texts come from
    the schema file, so an older run shows the sentence as it stands in the
    file today rather than a frozen copy."""
    aus: list[vm.BeratungshinweisAnsicht] = []
    for hid in getattr(pruefung, "beratungshinweise", []) or []:
        h = schema.hinweis(hid)
        if h is None:
            continue
        aus.append(vm.BeratungshinweisAnsicht(
            id=h.id, art=_vok(h.art), titel=h.titel,
            text=_zurueck(h.text, fall.pseudonyme),
            anker=_anker_roh(h.anker),
            geprueft_von=[
                vm.Fachpruefung(wer=f.wer, am=f.am, beleg=f.beleg, umfang=f.umfang,
                                vorbehalt=f.vorbehalt)
                for f in h.geprueft_von
            ],
        ))
    return aus


def _leitfaden(fall: Fall, schema: Schema) -> vm.LeitfadenPanel:
    """The Gesprächsleitfaden (14 §4 step 7) — no screen of its own (14 §6 says
    exactly two), a panel on the Fallakte. `leitfaden.fragen` already sorts the
    ones that can still move the assessment to the front; the projection keeps
    that order and only labels it."""
    from fallpruefer import leitfaden as lf

    fragen = [
        vm.LeitfadenFrage(
            pruefpunkt_id=f.pruefpunkt_id, pruefpunkt_titel=f.pruefpunkt_titel,
            text=f.text, typ=f.typ, fuellt=f.fuellt, werte=f.werte,
            feld_labels=f.feld_labels, wert_labels=f.wert_labels, hinweis=f.hinweis,
            status=_vok(Leitfadenstatus(f.status)), grund=f.grund,
            antwort=f.antwort,
            zustand=_vok(Zustand(f.zustand)) if f.zustand else None,
        )
        for f in lf.fragen(fall, schema)
    ]
    return vm.LeitfadenPanel(
        fragen=fragen,
        offen=sum(1 for f in fragen if f.status.code == Leitfadenstatus.OFFEN.value),
    )


def _fallgruppe_beleg(fall: Fall, pruefung: Pruefung, schema: Schema) -> vm.Zitat | None:
    """Der Satz, der die **bestätigte** Fallgruppe wirklich trägt.

    Bis zum 26. Aug stand im Zuordnungsfeld nur das Ticketzitat („mein Beitrag
    ab September … steigt"). Das belegt die Erhöhung — nicht den zweiten
    Halbsatz der Begründung, das Studio stütze sich auf eine AGB-Klausel. Es
    konnte ihn auch nicht belegen: `propose_fallgruppe(freitext, doktypen,
    taxonomie)` sieht die Dokumenttexte nicht, nur ihre Typen.

    Der Beleg existiert trotzdem — er hängt an der **Vorfrage** der Stufe 0
    (hier P0 „Anwendungsbereich / Regime"), deren Regel liest, worauf sich das
    Erhöhungsschreiben beruft. Deshalb die Regel hier: das erste Zitat des
    ersten `gate`-Prüfpunkts, der auf JA steht. Vor Gate 2 gibt es ihn nicht
    (dann läuft noch keine Prüfung unter diesem Schema), also steht er auch
    erst danach da — das Feld bleibt `None`, statt etwas zu behaupten.
    """
    if not fall.fallgruppe.bestaetigt:
        return None
    for erg in pruefung.ergebnisse:
        pp = schema.pruefpunkt(erg.pruefpunkt_id)
        if pp is None or pp.rolle != Rolle.GATE or erg.zustand != Zustand.JA:
            continue
        if erg.zitate:
            return _zitat(erg.zitate[0], fall.pseudonyme)
    return None


def bauen(fall: Fall, schema: Schema) -> vm.FallakteAnsicht:
    pruefung = fall.aktuelle_pruefung()
    if pruefung is None:
        raise ValueError(f"{fall.case_id}: keine Prüfung vorhanden")

    from fallpruefer.soll import auswerten as soll_auswerten

    k = Fallkontext(fall=fall, schema=schema)
    k.relevante_dokumente = soll_auswerten(fall, schema, k).massgebliche_dokumente()

    kopf = vm.Kopf(
        case_id=fall.case_id, ticket_nr=fall.eingang.ticket_nr, thema=fall.eingang.thema,
        kanal=_vok(fall.eingang.kanal), anbieter=fall.eingang.anbieter,
        gegner=fall.eingang.gegner, eingegangen_am=fall.eingang.eingegangen_am,
        status=_vok(fall.status),
        fallgruppe=_fallgruppe_vokabel(fall.schema_.fallgruppe_id),
        stufe=_vok(fall.fallgruppe.stufe or schema.stufe),
        fallgruppe_bestaetigt=fall.fallgruppe.bestaetigt,
        fallgruppe_vorschlag_fehlt=fall.fallgruppe.vorschlag_fehlt,
        fallgruppe_vorschlaege=[
            vm.FallgruppenVorschlag(
                fallgruppe=_fallgruppe_vokabel(v.id),
                stufe=_vok(Stufe(taxonomie().get(v.id, {}).get("stufe", "C"))),
                begruendung=v.begruendung,
                zitate=[_zitat(z, fall.pseudonyme) for z in v.zitate],
            )
            for v in fall.fallgruppe.vorschlaege
        ],
        fallgruppe_beleg=_fallgruppe_beleg(fall, pruefung, schema),
        schema_stopp_text=pruefung.schema_stopp_text,
        hinweis=konfig().texte.get(f"stufe_{schema.stufe.value.lower()}_hinweis")
        if schema.stufe != Stufe.A else None,
    )

    leitfaden = _leitfaden(fall, schema)
    beantwortet = frozenset(
        f.pruefpunkt_id for f in leitfaden.fragen if f.status.code != "offen"
    )
    return vm.FallakteAnsicht(
        case_id=fall.case_id,
        kopf=kopf,
        hero=_hero(pruefung, schema),
        offene_punkte=_offene_punkte(pruefung, schema, beantwortet),
        pruefpfad=_pruefpfad(pruefung, fall, schema, k),
        musterbrief=_musterbrief(fall, schema),
        nachforderungen=_nachforderungen(fall),
        laeufe=_laeufe(fall, schema),
        leitfaden=leitfaden,
        beratungshinweise=_beratungshinweise(pruefung, fall, schema),
        referat=_referat(fall, pruefung, k, schema),
        abschluss=vm.AbschlussPanel(
            basis_export_erzeugt=fall.abschluss.basis_export_erzeugt,
            basis_text=fall.abschluss.basis_text,
            wiedervorlagen=fall.abschluss.wiedervorlagen,
            geschlossen=fall.abschluss.geschlossen,
        ),
        dokumente=[
            vm.DokumentAnsicht(
                dok_id=TICKET_DOK_ID,
                dokumenttyp=Vokabel(code="ticket", label="Anliegen (Ticket)", tone="grau"),
                dateiname="Schilderung Ihres Anliegens",
                quelle=_vok(Quelle.VERBRAUCHER), eingegangen=_EINGEGANGEN["eingang"],
                typ_bestaetigt=True,
                seiten=[vm.Seite(nr=1, text_original=fall.eingang.freitext_original)],
            ),
            *[
            vm.DokumentAnsicht(
                dok_id=d.dok_id, dokumenttyp=_vok(d.dokumenttyp), dateiname=d.dateiname,
                quelle=_vok(d.quelle), eingegangen=_EINGEGANGEN.get(d.eingegangen, d.eingegangen),
                typ_bestaetigt=d.typ_bestaetigt,
                seiten=[vm.Seite(nr=s.nr, text_original=s.text_original) for s in d.seiten],
            )
            for d in fall.dokumente
            ],
        ],
        protokoll=_protokoll(fall),
        fusszeile=_fusszeile(fall, pruefung, schema),
    )
