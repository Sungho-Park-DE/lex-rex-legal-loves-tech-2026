---
{
  "id": "musterbrief_fitness_widerspruch",
  "titel": "Widerspruch gegen die Beitragserhöhung (formeller Mangel)",
  "fallgruppe_id": "preiserhoehung",
  "rechtsbehelf_id": "widerspruch_rueckforderung_vergangenheit",
  "empfaenger": "anbieter",
  "quelle": "eigen",
  "quelle_url": null,
  "quelle_datum": null,
  "hausstil_geprueft": false,
  "geprueft": false,
  "kommentar": "Der S4-Zweig: die Klausel selbst trägt, die Ausübung war formell mangelhaft (Vorlaufzeit, Form, fehlender Kündigungshinweis). Der Mangel ist heilbar — deshalb kein pauschaler Rückforderungsbetrag im Text, sondern die Beträge bis zu einer ordnungsgemäßen Ankündigung. Schwestervorlage zu musterbrief_fitness_widerspruch_rueckforderung, die den materiellen Fall abdeckt.",
  "varianten": [
    {"id": "kein_kuendigungshinweis", "wenn": {"feld": "erhoehungsschreiben.kuendigungshinweis", "op": "==", "wert": false}},
    {"id": "vorlaufzeit", "wenn": {"feld": "pruefpunkt.P10.zustand", "op": "in", "wert": ["NEIN", "WERTUNG"]}},
    {"id": "form", "wenn": {"feld": "erhoehungsschreiben.form", "op": "in", "wert": ["aushang", "website"]}}
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

mit Schreiben vom [SCHREIBEN_DATUM] haben Sie mir mitgeteilt, dass sich mein monatlicher Beitrag ab dem [ERHOEHUNG_AB] auf [NEUER_BEITRAG] erhöht. Der Erhöhung widerspreche ich hiermit.

<!-- variante: vorlaufzeit -->
Zwischen dem Zugang Ihrer Mitteilung und dem genannten Termin lag keine angemessene Vorlaufzeit. Mir blieb damit keine ausreichende Gelegenheit, auf die Erhöhung zu reagieren.
<!-- /variante -->

<!-- variante: form -->
Hinzu kommt, dass Sie die Erhöhung nicht mir persönlich mitgeteilt, sondern lediglich allgemein bekannt gemacht haben. Eine Änderung meines Beitrags muss mich als Vertragspartnerin erreichen.
<!-- /variante -->

<!-- variante: kein_kuendigungshinweis -->
Ihr Schreiben weist mich außerdem nicht auf das Kündigungsrecht hin, das Ihre eigenen Bedingungen für den Fall einer Beitragsanpassung vorsehen.
<!-- /variante -->

Bis zu einer ordnungsgemäßen Ankündigung bleibt es bei dem bisher vereinbarten Beitrag. Bereits eingezogene Mehrbeträge fordere ich zurück; bitte erstatten Sie sie bis zum [FRIST_ENDE] auf mein Ihnen bekanntes Konto.

Bitte bestätigen Sie mir bis zum [FRIST_ENDE] schriftlich, wie Sie weiter verfahren.

Mit freundlichen Grüßen


[NAME]
