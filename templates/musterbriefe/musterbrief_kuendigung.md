---
{
  "id": "musterbrief_kuendigung",
  "titel": "Kündigung des Mitgliedsvertrages",
  "fallgruppe_id": "preiserhoehung",
  "rechtsbehelf_id": "kuendigung_bei_wirksam",
  "empfaenger": "anbieter",
  "quelle": "eigen",
  "quelle_url": null,
  "quelle_datum": null,
  "hausstil_geprueft": false,
  "geprueft": false,
  "kommentar": "Der wirksam-Zweig. Beide Varianten sind bewusst gleichzeitig hinterlegt (15 §13): Franz' Aufgabe 3 entscheidet, ob bei einer wirksamen Erhöhung ein Sonderkündigungsrecht besteht oder nur die ordentliche Kündigung bleibt. Die Bedingung liest nicht die Rechtslage, sondern die Klausel: räumt die Preisklausel selbst ein Kündigungsrecht ein, greift die Sonderkündigung; sonst die ordentliche. Kommt seine Antwort, ändert sich diese Datei — kein Code.",
  "varianten": [
    {"id": "sonderkuendigung", "wenn": {"feld": "agb.kuendigungsrecht_bei_erhoehung", "op": "==", "wert": true}},
    {"id": "ordentlich", "wenn": {"eine": [{"feld": "agb.kuendigungsrecht_bei_erhoehung", "op": "==", "wert": false}, {"fehlt": "agb.kuendigungsrecht_bei_erhoehung"}]}}
  ]
}
---
[NAME]
[ANSCHRIFT]

[ANBIETER]
[ANBIETER_ANSCHRIFT]

[HEUTE]

Kündigung meines Mitgliedsvertrages vom [VERTRAGSDATUM] — Kundennummer [KUNDENNUMMER]

Sehr geehrte Damen und Herren,

mit Schreiben vom [SCHREIBEN_DATUM] haben Sie mir mitgeteilt, dass sich mein monatlicher Beitrag ab dem [ERHOEHUNG_AB] auf [NEUER_BEITRAG] erhöht.

<!-- variante: sonderkuendigung -->
Von dem Kündigungsrecht, das Ihre Bedingungen für den Fall einer Beitragsanpassung vorsehen, mache ich hiermit Gebrauch: Ich kündige meinen Mitgliedsvertrag zum [ERHOEHUNG_AB], hilfsweise zum nächstmöglichen Zeitpunkt. Zu dem erhöhten Beitrag möchte ich den Vertrag nicht fortsetzen.
<!-- /variante -->

<!-- variante: ordentlich -->
Ich möchte den Vertrag zu diesem Beitrag nicht fortsetzen und kündige ihn hiermit ordentlich zum nächstmöglichen Zeitpunkt.
<!-- /variante -->

Bitte bestätigen Sie mir bis zum [FRIST_ENDE] schriftlich den Eingang dieser Kündigung und das Datum, zu dem der Vertrag endet. Bitte stellen Sie außerdem sicher, dass über das Vertragsende hinaus keine Beiträge mehr eingezogen werden.

Mit freundlichen Grüßen


[NAME]
