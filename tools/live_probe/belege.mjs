/**
 * Erzeugt die drei `k60a_*`-Belegaufnahmen nach `analysis/28_belege/`.
 *
 * ⚠️ Die Falle, gegen die dieses Skript sich wehrt (llt26-ac, 26. Aug): in den
 * Zwischenstufen derselben Messung waren `shots/chip_gegengelesen.png` und
 * `shots/chip_ungeprueft.png` **byteidentisch** — zwei Aufnahmen, die den
 * Unterschied zeigen sollten, waren dasselbe Bild. Exit 0, Dateien da, Inhalt
 * falsch. Wer daraus einen Schluss zieht, zieht ihn aus einer Aufnahme zweimal.
 *
 * Deshalb hier zwei Nägel statt eines festen Timeouts:
 *   1. vor jeder Popover-Aufnahme wird auf den **Textinhalt** gewartet, der
 *      darin stehen muss — nicht auf eine Sekundenzahl;
 *   2. am Ende werden die geschriebenen Dateien gehasht, und zwei gleiche
 *      Hashes sind ein Abbruch mit Exit 1, kein Achselzucken.
 *
 * Aufruf:  node belege.mjs F-2026-01xx      (frischer Fall, Backend + UI laufen)
 */
import { chromium } from "playwright";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const ZIEL = new URL("../../analysis/28_belege", import.meta.url).pathname;
const fall = process.argv[2];
if (!fall) throw new Error("Aufruf: node belege.mjs F-2026-01xx");

const b = await chromium.launch();
const s = await b.newPage({ viewport: { width: 1440, height: 900 } });
const geschrieben = [];

async function aufnehmen(datei) {
  const pfad = `${ZIEL}/${datei}`;
  await s.screenshot({ path: pfad });
  geschrieben.push(datei);
  return pfad;
}

try {
  await s.goto(`http://localhost:8080/faelle/${fall}`, { waitUntil: "networkidle" });
  if (await s.locator("text=Demo-Modus").count()) throw new Error("Fixture-Modus erwischt — Backend prüfen");
  await s.locator('nav[aria-label="Schritte"] button').nth(3).click();
  await s.waitForTimeout(500);
  for (const kn of await s.locator('button:has-text("alle aufklappen")').all()) await kn.click();
  await s.waitForTimeout(700);

  // 1) die Chipreihe, ohne offenes Popover.
  //
  // Auch hier kein Warten auf die Uhr (llt26-ac, 26. Aug): der Hashvergleich
  // am Ende fängt nur zwei *gleiche* Belege. Eine falsch erwischte Aufnahme 1
  // — Popover vom vorigen Lauf noch offen, „alle aufklappen" noch nicht
  // durchgerendert — ist von den anderen verschieden und käme sauber durch.
  // Das Bild behauptet etwas Prüfbares, also wird genau das vorher zugesichert.
  await s.evaluate(() => {
    const el = [...document.querySelectorAll("button")].find((e) => e.textContent?.includes("13 O 730/22"));
    el?.scrollIntoView({ block: "center" });
  });
  await s.locator("[data-radix-popper-content-wrapper]").waitFor({ state: "detached", timeout: 5000 });
  const reihe = await s.evaluate(() => {
    const chips = [...document.querySelectorAll("button")].filter((e) =>
      /^(§|BGH|LG |OLG )/.test((e.textContent ?? "").trim()),
    );
    return { anzahl: chips.length, mitWort: chips.filter((e) => e.textContent.includes("Fundstelle")).length };
  });
  if (reihe.anzahl === 0) throw new Error("keine Anker-Chips sichtbar — Baum nicht aufgeklappt?");
  if (reihe.mitWort > 0)
    throw new Error(
      `${reihe.mitWort} von ${reihe.anzahl} Anker-Chips tragen wieder „Fundstelle …" — ` +
        "das Bild würde das Gegenteil dessen zeigen, was es belegen soll (K60a).",
    );
  await aufnehmen("k60a_ankerchip_ohne_wort.png");
  console.log(`k60a_ankerchip_ohne_wort.png  ${reihe.anzahl} Anker-Chips, ${reihe.mitWort} mit Prüfstandswort`);

  // 2+3) die zwei Popover — je mit dem Satz, der darin stehen MUSS
  const faelle = [
    ["geprueft", "13 O 730/22", "Fundstelle gegengelesen"],
    ["ungeprueft", "305c", "Fundstelle ungeprüft"],
  ];
  for (const [name, treffer, muss] of faelle) {
    const info = await s.evaluate((treffer) => {
      const el = [...document.querySelectorAll("button")].find((e) => e.textContent?.includes(treffer));
      if (!el) return null;
      el.scrollIntoView({ block: "center" });
      el.click();
      return { chip: el.textContent.trim(), gestrichelt: el.className.includes("border-dashed") };
    }, treffer);
    if (!info) throw new Error(`Chip "${treffer}" nicht gefunden`);
    // Der Nagel: warten, bis der geforderte Satz sichtbar ist. Steht er nicht
    // da, bricht es hier ab — statt die vorherige Seite zu fotografieren.
    await s.locator(`[data-radix-popper-content-wrapper]:has-text("${muss}")`).first().waitFor({ timeout: 5000 });
    await aufnehmen(`k60a_popover_${name}.png`);
    console.log(`k60a_popover_${name}.png  Chip "${info.chip}"  border-dashed=${info.gestrichelt}  enthält „${muss}"`);
    await s.keyboard.press("Escape");
    await s.waitForTimeout(300);
  }
} finally {
  await b.close();
}

// Der zweite Nagel: keine zwei Belege dürfen dasselbe Bild sein.
const hashes = new Map();
for (const datei of geschrieben) {
  const h = createHash("md5").update(readFileSync(`${ZIEL}/${datei}`)).digest("hex");
  if (hashes.has(h)) {
    console.error(`\nABBRUCH: ${datei} ist byteidentisch mit ${hashes.get(h)} — der Beleg zeigt zweimal dasselbe.`);
    process.exit(1);
  }
  hashes.set(h, datei);
  console.log(`  ${h.slice(0, 8)}  ${datei}`);
}
console.log(`\n${geschrieben.length} Aufnahmen, ${hashes.size} verschiedene — in Ordnung.`);
