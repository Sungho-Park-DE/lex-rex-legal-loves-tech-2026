/**
 * Gegenprobe am DOM zu `tools/anker_zaehlen.py`.
 *
 * Das Python-Skript zählt im **Fixture**, dieses hier im **laufenden Schirm** —
 * beide müssen dieselbe Zahl liefern, und wenn nicht, ist das ein Befund.
 * Genau so ist am 26. Aug aufgefallen, dass eine gemeldete Chipzahl vier
 * Prüfpunkt-Titel mitzählte: der lockere Filter (`§` irgendwo im Text) traf
 * auch Zeilen wie „Erklärungsfiktion (§ 308 Nr. 5)", der strenge
 * (`button[aria-haspopup="dialog"]`, Text beginnt mit § / BGH / LG / OLG) nicht.
 * Beide Zählweisen werden deshalb ausgegeben, nicht nur die richtige.
 *
 * ⚠️ Die Zahl gehört immer an ihren **Fall** — drehkreuz trägt 20 Instanzen,
 * seepark und nordlicht 17. Eine Chipzahl ohne Fallnamen ist keine Aussage.
 *
 * Aufruf:  node zaehl.mjs F-2026-01xx      (Backend + UI laufen, frischer Fall)
 */
import { chromium } from "playwright";
const b = await chromium.launch();
const s = await b.newPage({ viewport: { width: 1440, height: 900 } });
await s.goto(`http://localhost:8080/faelle/${process.argv[2]}`, { waitUntil: "networkidle" });
await s.locator('nav[aria-label="Schritte"] button').nth(3).click();
await s.waitForTimeout(500);
for (const kn of await s.locator('button:has-text("alle aufklappen")').all()) await kn.click();
await s.waitForTimeout(800);
const r = await s.evaluate(() => {
  // Der echte Anker-Chip ist ein Popover-Trigger; die Prüfpunkt-Titel sind es nicht.
  const chips = [...document.querySelectorAll('button[aria-haspopup="dialog"]')].filter((e) =>
    /^(§|BGH|LG |OLG )/.test((e.textContent ?? "").trim()));
  const locker = [...document.querySelectorAll("button")].filter((e) => /§|BGH|LG |OLG /.test(e.textContent ?? ""));
  return {
    echte: chips.length,
    echte_liste: chips.map((e) => e.textContent.trim()),
    lockere_zaehlung: locker.length,
    lockere_dedupliziert: new Set(locker.map((e) => e.textContent.trim())).size,
    geprueft: chips.filter((e) => !e.className.includes("border-dashed")).length,
  };
});
console.log("echte Anker-Chips (Popover-Trigger):", r.echte);
console.log("davon durchgezogener Rahmen (geprueft):", r.geprueft);
console.log("lockere Zaehlung wie in anker.mjs:", r.lockere_zaehlung, "/ dedupliziert:", r.lockere_dedupliziert);
console.log("Liste:"); r.echte_liste.forEach((t) => console.log("   " + t));
await b.close();
