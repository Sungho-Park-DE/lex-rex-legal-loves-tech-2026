import { chromium } from "playwright";
const b = await chromium.launch();
const s = await b.newPage({ viewport: { width: 1440, height: 900 } });
await s.goto(`http://localhost:8080/faelle/${process.argv[2]}`, { waitUntil: "networkidle" });
await s.locator('nav[aria-label="Schritte"] button').nth(3).click();
await s.waitForTimeout(500);
for (const kn of await s.locator('button:has-text("alle aufklappen")').all()) await kn.click();
await s.waitForTimeout(600);
const chips = await s.evaluate(() =>
  [...document.querySelectorAll("button")]
    .filter((e) => /§|BGH|LG |OLG /.test(e.textContent ?? ""))
    .map((e) => e.textContent.trim().replace(/\s+/g, " "))
    .filter((t, i, a) => a.indexOf(t) === i),
);
console.log(`Anker-Chips auf dem Schirm: ${chips.length}`);
for (const c of chips) console.log("  " + c);
const bamberg = s.locator('button:has-text("13 O 730/22")').first();
if (await bamberg.count()) {
  await bamberg.scrollIntoViewIfNeeded();
  await bamberg.click();
  await s.waitForTimeout(500);
  const pop = await s.locator('[data-state="open"][role="dialog"], [data-radix-popper-content-wrapper]').first().textContent();
  console.log("\nPopover LG Bamberg:", pop?.replace(/\s+/g, " ").slice(0, 260));
  await s.screenshot({ path: "shots/k60_bamberg_gegengelesen.png" });
}
await b.close();
