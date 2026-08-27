---
{
  "id": "musterbrief_fitness_widerspruch_rueckforderung",
  "titel": "Widerspruch gegen die Beitragserhöhung",
  "fallgruppe_id": "preiserhoehung",
  "rechtsbehelf_id": "widerspruch_rueckforderung",
  "empfaenger": "anbieter",
  "quelle": "eigen",
  "quelle_url": null,
  "quelle_datum": null,
  "hausstil_geprueft": false,
  "geprueft": false,
  "kommentar": "Platzhalter bis Paulinas VZ-Musterbrief-Downloads eintreffen (15 §13). Dann: Datei ersetzen, quelle auf vz_musterbrief, quelle_url setzen — kein Code ändert sich.",
  "varianten": [
    {"id": "preisgarantie", "wenn": {"feld": "pruefpunkt.P3.zustand", "op": "==", "wert": "NEIN"}},
    {"id": "intransparent", "wenn": {"feld": "pruefpunkt.P6.zustand", "op": "==", "wert": "NEIN"}},
    {"id": "keine_senkungspflicht", "wenn": {"feld": "pruefpunkt.P7.zustand", "op": "==", "wert": "NEIN"}},
    {"id": "zustimmungsfiktion", "wenn": {"eine": [{"feld": "pruefpunkt.P9.zustand", "op": "==", "wert": "NEIN"}, {"feld": "pruefpunkt.P8.zustand", "op": "==", "wert": "NEIN"}]}},
    {"id": "einbeziehung", "wenn": {"feld": "pruefpunkt.P2.zustand", "op": "==", "wert": "NEIN"}},
    {"id": "keine_grundlage", "wenn": {"feld": "pruefpunkt.P1.zustand", "op": "==", "wert": "NEIN"}},
    {"id": "mit_rueckforderung", "wenn": {"vorhanden": "berechnung.rueckforderung"}},
    {"id": "ohne_rueckforderung", "wenn": {"fehlt": "berechnung.rueckforderung"}}
  ]
}
---
[NAME]
[ANSCHRIFT]

[ANBIETER]
[ANBIETER_ANSCHRIFT]

[HEUTE]

Widerspruch gegen die Beitragserhöhung — Kundennummer [KUNDENNUMMER]

Sehr geehrte Damen und Herren,

mit Schreiben vom [SCHREIBEN_DATUM] haben Sie mir mitgeteilt, dass sich mein monatlicher Beitrag ab dem [ERHOEHUNG_AB] von [ALTER_BEITRAG] auf [NEUER_BEITRAG] erhöht. Der Erhöhung widerspreche ich hiermit. Es bleibt bei dem im Vertrag vom [VERTRAGSDATUM] vereinbarten Beitrag von [ALTER_BEITRAG].

<!-- variante: keine_grundlage -->
Ihrem Schreiben lässt sich nicht entnehmen, worauf Sie das Recht zur Erhöhung stützen. Ohne eine wirksame Grundlage können Sie den vereinbarten Beitrag nicht einseitig ändern.
<!-- /variante -->

<!-- variante: einbeziehung -->
Die Klausel, auf die Sie sich berufen, war in dieser Fassung bei meinem Vertragsschluss nicht vereinbart. Sie ist damit nicht Bestandteil meines Vertrages geworden.
<!-- /variante -->

<!-- variante: preisgarantie -->
In meinem Vertrag ist der Beitrag ausdrücklich für einen bestimmten Zeitraum zugesichert. Diese individuelle Abrede geht Ihren Allgemeinen Geschäftsbedingungen vor, und die Erhöhung fällt in den zugesicherten Zeitraum.
<!-- /variante -->

<!-- variante: intransparent -->
Die Klausel, auf die Sie sich stützen, lässt nicht erkennen, aus welchem Anlass, unter welchen Voraussetzungen und in welchem Umfang der Beitrag erhöht werden darf. Eine Preisanpassungsklausel, die das offenlässt, benachteiligt mich unangemessen.
<!-- /variante -->

<!-- variante: keine_senkungspflicht -->
Die Klausel verpflichtet Sie außerdem nicht, gesunkene Kosten ebenso weiterzugeben, wie Sie gestiegene Kosten weitergeben. Eine solche einseitige Regelung halte ich für unwirksam.
<!-- /variante -->

<!-- variante: zustimmungsfiktion -->
Mein Einverständnis mit der Erhöhung liegt nicht vor. Weder mein Schweigen noch die weitere Nutzung des Studios ist eine Zustimmung zu einem höheren Beitrag.
<!-- /variante -->

<!-- variante: mit_rueckforderung -->
Die seit dem [ERHOEHUNG_AB] zu viel eingezogenen Beträge in Höhe von insgesamt [RUECKFORDERUNG_BETRAG] fordere ich zurück. Bitte überweisen Sie diesen Betrag bis zum [FRIST_ENDE] auf mein Ihnen bekanntes Konto.
<!-- /variante -->

<!-- variante: ohne_rueckforderung -->
Sollten Sie den erhöhten Beitrag dennoch einziehen, fordere ich die Differenz schon jetzt zurück.
<!-- /variante -->

Bitte bestätigen Sie mir bis zum [FRIST_ENDE] schriftlich, dass es bei dem bisherigen Beitrag bleibt.

Mit freundlichen Grüßen


[NAME]
