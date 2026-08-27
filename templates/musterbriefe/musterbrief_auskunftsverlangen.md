---
{
  "id": "musterbrief_auskunftsverlangen",
  "titel": "Zahlung unter Vorbehalt und Auskunftsverlangen",
  "fallgruppe_id": "preiserhoehung",
  "rechtsbehelf_id": [
    "bestreiten_nachweise_verlangen",
    "auskunftsverlangen_vorbehalt"
  ],
  "empfaenger": "anbieter",
  "quelle": "eigen",
  "quelle_url": null,
  "quelle_datum": null,
  "hausstil_geprueft": false,
  "geprueft": false,
  "kommentar": "Eine Datei, zwei Rechtsbehelfe (15 §2 rechtsbehelfe.liste): bestreiten_nachweise_verlangen im unklar-Zweig und auskunftsverlangen_vorbehalt im wirksam-Zweig zeigen auf dieselbe Vorlage. Die Varianten trennen nur das Register — im unklar-Zweig fehlen der Beraterin die Unterlagen der Unternehmensseite, im wirksam-Zweig bleibt die Frage nach der Höhe (§ 315 BGB) offen. Nur Platzhalter aus dem Erhöhungsschreiben, weil in beiden Zweigen genau das sicher vorliegt.",
  "varianten": [
    {
      "id": "nachweise_verlangen",
      "wenn": {
        "feld": "einordnung",
        "op": "==",
        "wert": "unklar – es fehlt …"
      }
    },
    {
      "id": "unter_vorbehalt",
      "wenn": {
        "feld": "einordnung",
        "op": "==",
        "wert": "wirksam"
      }
    },
    {
      "id": "kostenbegruendung",
      "wenn": {
        "feld": "pruefpunkt.P11.zustand",
        "op": "==",
        "wert": "FEHLT"
      }
    }
  ],
  "frist_tage": 28,
  "frist_begruendung": "VZ-Hausstil (22 §8): vier Wochen für eine Auskunft, 14 Tage für eine Rückzahlung."
}
---
[NAME]
[ANSCHRIFT]

[ANBIETER]
[ANBIETER_ANSCHRIFT]

[HEUTE]

Ihre Beitragsanpassung vom [SCHREIBEN_DATUM] — Kundennummer [KUNDENNUMMER]

Sehr geehrte Damen und Herren,

mit Schreiben vom [SCHREIBEN_DATUM] haben Sie mir mitgeteilt, dass sich mein monatlicher Beitrag ab dem [ERHOEHUNG_AB] auf [NEUER_BEITRAG] erhöht.

<!-- variante: unter_vorbehalt -->
Weitere Zahlungen leiste ich ab dem [ERHOEHUNG_AB] ausdrücklich ohne Anerkennung einer Rechtspflicht und unter Vorbehalt der Rückforderung. Aus der Zahlung des erhöhten Beitrags folgt kein Einverständnis mit seiner Höhe.
<!-- /variante -->

<!-- variante: nachweise_verlangen -->
Bevor ich die Erhöhung hinnehme, benötige ich die Grundlagen, auf die Sie sie stützen. Bitte übersenden Sie mir die bei meinem Vertragsschluss geltenden Allgemeinen Geschäftsbedingungen vollständig sowie die Klausel, auf die Sie sich berufen, im Wortlaut.

Sie berufen sich auf diese Klausel, also ist es an Ihnen darzulegen, dass sie in meinen Vertrag einbezogen wurde und wie sie zu diesem Zeitpunkt lautete. Ein Hinweis auf Unterlagen, die mir nicht vorliegen, genügt dafür nicht.
<!-- /variante -->

<!-- variante: kostenbegruendung -->
Bitte legen Sie mir außerdem nachvollziehbar dar, welche Kosten sich seit meinem Vertragsschluss in welchem Umfang verändert haben und wie sich daraus die Höhe der Erhöhung ergibt. Ohne diese Angaben kann ich nicht nachvollziehen, ob die gewählte Höhe der Kostenentwicklung entspricht.
<!-- /variante -->

Bitte antworten Sie mir bis zum [FRIST_ENDE]. Sollten Sie die erbetenen Unterlagen und Angaben bis dahin nicht vorlegen, behalte ich mir weitere Schritte vor.

Mit freundlichen Grüßen


[NAME]
