import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

// Die 12-Schritte-Live-Probe aus 27 §3 — als Skript, weil sie zweimal in
// einem Tag von Hand laufen musste und beim ersten Mal (28 F1) vier tote
// Gates fand, die 343 grüne Tests nicht sehen konnten. Fixture-Modus kann
// POSTs prinzipbedingt nicht prüfen; nur das hier tut es.
//
//   node probe.mjs <case_id> [ausgabe-ordner] [nachreichungsdatei]
//
// Voraussetzungen: Backend auf :8000 (HEAD!), UI auf :8080 mit
// VITE_API_BASE_URL, ein FRISCHER Fall (tools/demo_start.py legt einen an).
// Bestanden heisst: alle POSTs 2xx, "/aktionen/" kommt nie vor, Statuszeile
// zeigt am Ende "wirksam", Abschluss "Fall geschlossen".
// Danach: tools/radar_seed.py --zuruecksetzen — Gate 3 hat den Store beruehrt.
const CASE = process.argv[2];
if (!CASE) { console.error("case_id fehlt: node probe.mjs F-2026-01xx [ordner] [datei]"); process.exit(2); }
const OUT = process.argv[3] ?? "shots";
const NACHREICHUNG = process.argv[4]
  ?? process.env.HOME + "/dev/llt26/demo/faelle/seepark_seite_fehlt/bedingungen_seite2_nachgereicht.md";
const UI = process.env.PROBE_UI ?? "http://localhost:8080";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });

const posts = [];
const konsole = [];
page.on("response", (r) => {
  const m = r.request().method();
  if (m === "POST") posts.push(`${r.status()} ${m} ${r.url()}`);
});
page.on("console", (m) => { if (m.type() === "error") konsole.push(m.text()); });
page.on("pageerror", (e) => konsole.push("PAGEERROR: " + e.message));

let n = 0;
const shot = async (name) => {
  n += 1;
  const p = `${OUT}/${String(n).padStart(2, "0")}_${name}.png`;
  await page.screenshot({ path: p, fullPage: true });
  return p;
};
const log = (...a) => console.log(...a);

// Die Schritt-Leiste ist ein eigenes <nav> — sonst kollidiert /Unterlagen/ mit
// „Unterlagen nachreichen" und /Einordnung/ mit „Einordnung bestätigen" (27 §3).
const rail = page.locator('nav[aria-label="Schritte"]');
const gehe = async (re, label) => {
  await rail.getByRole("button", { name: re }).click();
  await page.waitForTimeout(600);
  log(`   → Rail: ${label}`);
};

await page.goto(`${UI}/faelle/${CASE}`, { waitUntil: "domcontentloaded", timeout: 45000 });
await page.waitForTimeout(2000);

// --- Live-Modus? ---
const demoBadge = await page.getByText("Demo-Modus").count();
log(`MODUS: ${demoBadge === 0 ? "LIVE (kein Demo-Badge)" : "!!! FIXTURE-MODUS !!!"}`);
if (demoBadge !== 0) { await browser.close(); process.exit(1); }

// (1) Startzustand
log("\n(1) Startzustand");
log("   Hero:", (await page.locator("body").innerText()).split("\n").slice(0, 12).join(" | ").slice(0, 220));
log("   " + await shot("start_unklar"));

// (2) Gate 2
log("\n(2) Gate 2 — Fallgruppe bestätigen");
const g2 = page.getByRole("button", { name: /Fallgruppe bestätigen/ });
log("   Knopf sichtbar:", await g2.count());
await g2.click();
await page.waitForTimeout(1500);
log("   Knopf danach:", await g2.count(), "(0 = verschwunden, wie UI-Grammatik verlangt)");
log("   " + await shot("gate2_bestaetigt"));

// (3) Schritt 2 — Leitfaden
log("\n(3) Schritt 2 — Leitfaden P14");
await gehe(/Offene Punkte/, "Offene Punkte & Gespräch");
log("   " + await shot("schritt2_leitfaden"));
const p14 = page.locator('li', { hasText: "Seit wie vielen Monaten" }).locator("input").last();
await p14.fill("8");
await page.waitForTimeout(300);
const uebern = page.getByRole("button", { name: /Antworten übernehmen/ });
log("   'Antworten übernehmen' aktiv:", await uebern.isEnabled());
await uebern.click();
await page.waitForTimeout(3000);
const lfText = await page.locator("body").innerText();
log("   Leitfaden 'offen'-Zähler jetzt:", (lfText.match(/(\d+) offen/) ?? [])[1]);
log("   " + await shot("leitfaden_uebernommen"));

// (4) Gate 1
log("\n(4) Schritt 3 — Gate 1: Nachforderung erzeugen");
await gehe(/Unterlagen/, "Unterlagen");
const erz = page.getByRole("button", { name: /Nachforderung erzeugen/ });
await erz.click();
await page.waitForTimeout(2000);
const nachText = await page.locator("body").innerText();
log("   'Keine Nachforderung erzeugt.' noch da:", nachText.includes("Keine Nachforderung erzeugt."));
log("   N1 sichtbar:", /\bN1\b/.test(nachText));
log("   Upload-Formular:", await page.locator('button:has-text("Unterlagen nachreichen")').count());
log("   " + await shot("gate1_n1"));

const mark = page.getByRole("button", { name: /als angefordert markieren/ });
log("   'als angefordert markieren' vorhanden:", await mark.count());
if (await mark.count()) { await mark.first().click(); await page.waitForTimeout(1500); }
log("   " + await shot("gate1_markiert"));

// (5) Nachreichung
log("\n(5) Unterlagen nachreichen");
await page.setInputFiles('input[type="file"]', NACHREICHUNG);
await page.waitForTimeout(400);
await page.locator('button:has-text("Unterlagen nachreichen")').click();
await page.waitForTimeout(4000);
log("   " + await shot("nachgereicht"));

// (6) Flip
log("\n(6) Flip prüfen");
await gehe(/Einordnung/, "Einordnung");
const heroText = (await page.locator("body").innerText()).slice(0, 400);
log("   Statuszeile:", heroText.split("\n").filter(Boolean).slice(0, 10).join(" | ").slice(0, 260));
log("   " + await shot("flip_hero"));

// (7) Gate 4
log("\n(7) Schritt 5 — Gate 4: Rechtsbehelf übernehmen");
await gehe(/Musterbrief/, "Musterbrief");
log("   " + await shot("musterbrief_vorher"));
const g4 = page.getByRole("button", { name: /Rechtsbehelf übernehmen/ });
log("   Knopf:", await g4.count());
await g4.click();
await page.waitForTimeout(2500);
log("   " + await shot("gate4_uebernommen"));

// (8) Gate 3
log("\n(8) Schritt 1 — Gate 3: Einordnung bestätigen");
await gehe(/Einordnung/, "Einordnung");
const g3 = page.getByRole("button", { name: /Einordnung bestätigen/ });
log("   Knopf:", await g3.count());
if (await g3.count()) { await g3.click(); await page.waitForTimeout(2000); }
log("   " + await shot("gate3_bestaetigt"));

// (9) Referat
log("\n(9) Schritt 6 — Referat markieren");
await gehe(/Abschluss/, "Abschluss");
const boxen = page.locator('input[type="checkbox"]');
const anz = await boxen.count();
log("   Checkboxen:", anz);
for (let i = 0; i < Math.min(anz, 2); i += 1) await boxen.nth(i).check();
await page.waitForTimeout(300);
const refKnopf = page.getByRole("button", { name: /Für Referat markieren/ });
log("   Referat-Knopf:", await refKnopf.count());
if (await refKnopf.count()) { await refKnopf.first().click(); await page.waitForTimeout(2000); }
log("   " + await shot("referat_markiert"));

// (12) Abschluss
log("\n(12) Fall abschließen");
const ab = page.getByRole("button", { name: /Fall abschließen/ });
log("   Knopf:", await ab.count());
await ab.click();
await page.waitForTimeout(2500);
const abText = await page.locator("body").innerText();
log("   'Fall geschlossen' im Panel:", abText.includes("Fall geschlossen"));
log("   Knopfbeschriftung jetzt 'geschlossen':", await page.getByRole("button", { name: /^geschlossen$/ }).count());
log("   " + await shot("abschluss_geschlossen"));

// (11) Protokoll
log("\n(11) Protokoll");
const prot = await page.locator("body").innerText();
for (const s of ["gate2", "nachforderung", "gate3", "rechtsbehelf", "referat", "geschlossen", "nachreichung"]) {
  log(`   enthält "${s}":`, prot.toLowerCase().includes(s));
}
log("   " + await shot("protokoll"));

// (10) Referat-Seite
log("\n(10) /referat");
await page.goto(`${UI}/referat`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
log("   " + await shot("referat_seite"));

log("\n================ POST-LOG ================");
posts.forEach((p) => log(" ", p));
log("  /aktionen/ kommt vor:", posts.some((p) => p.includes("/aktionen/")));
log("  nicht-2xx POSTs:", posts.filter((p) => !/^2\d\d /.test(p)).length || "keine");
log("\nKONSOLENFEHLER:", konsole.length ? konsole.slice(0, 8) : "keine");

await browser.close();
const bestanden = !posts.some((p) => p.includes("/aktionen/"))
  && posts.every((p) => /^2\d\d /.test(p))
  && posts.length >= 8;
log(bestanden ? "\nPROBE BESTANDEN" : "\nPROBE NICHT BESTANDEN");
process.exit(bestanden ? 0 : 1);
