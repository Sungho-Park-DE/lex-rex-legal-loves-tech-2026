import { chromium } from "playwright";
import { execSync } from "node:child_process";
const fall = process.argv[2];
const SCHEMA = new URL("../../schemas/preiserhoehung.json", import.meta.url).pathname;
const SICHERUNG = "/tmp/preiserhoehung_b3_backup.json";
execSync(`cp ${SCHEMA} ${SICHERUNG}`);  // vor jedem Lauf frisch, damit finally sicher zurueckschreibt
const b = await chromium.launch();
const s = await b.newPage({ viewport: { width: 1440, height: 900 } });
const stufen = async () =>
  s.evaluate(() =>
    [...document.querySelectorAll('button[aria-expanded]')]
      .filter((e) => e.textContent?.trim() && e.querySelector("svg"))
      .map((e) => ({
        titel: (e.querySelector("span.font-medium")?.textContent ?? e.textContent ?? "").trim().slice(0, 40),
        offen: e.getAttribute("aria-expanded") === "true",
      })),
  );
try {
  await s.goto(`http://localhost:8080/faelle/${fall}`, { waitUntil: "networkidle" });
  await s.locator('nav[aria-label="Schritte"] button').nth(3).click();
  await s.waitForTimeout(500);
  console.log("1) Voreinstellung:", JSON.stringify(await stufen(), null, 0));

  // Die Beraterin klappt von Hand alles zu — der strenge Fall.
  for (const kn of await s.locator('button[aria-expanded="true"]').all()) {
    if (await kn.locator("svg").count()) await kn.click();
  }
  await s.waitForTimeout(300);
  console.log("2) alles von Hand zu:", JSON.stringify(await stufen(), null, 0));

  // Jurist-Edit (Regiebuch B2): 30 -> 90, Fassung 0.7.0 -> 0.7.1
  let txt = execSync(`cat ${SCHEMA}`).toString();
  txt = txt.replace('"frist_min_tage": 30', '"frist_min_tage": 90').replace('"version": "0.7.0"', '"version": "0.7.1"');
  execSync(`cat > ${SCHEMA}`, { input: txt });
  await s.waitForTimeout(1200);

  await s.locator('button:has-text("Prüfschema neu einlesen")').first().click();
  await s.waitForTimeout(2000);
  console.log("3) nach neu einlesen:", JSON.stringify(await stufen(), null, 0));
  const einordnung = await s.locator('[aria-label="Aktuelle Einordnung"]').first().textContent();
  console.log("   Einordnung:", einordnung?.trim().slice(0, 90));
  await s.screenshot({ path: "shots/b3_nach_edit.png", fullPage: false });
} finally {
  execSync(`cp /tmp/preiserhoehung_b3_backup.json ${SCHEMA}`);
  console.log("Schema zurückgesetzt:", execSync(`grep -c '"frist_min_tage": 30' ${SCHEMA}`).toString().trim(), "Treffer auf 30");
  await b.close();
}
