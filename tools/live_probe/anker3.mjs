import { chromium } from "playwright";
const b = await chromium.launch();
const s = await b.newPage({ viewport: { width: 1440, height: 900 } });
await s.goto(`http://localhost:8080/faelle/${process.argv[2]}`, { waitUntil: "networkidle" });
await s.locator('nav[aria-label="Schritte"] button').nth(3).click();
await s.waitForTimeout(500);
for (const kn of await s.locator('button:has-text("alle aufklappen")').all()) await kn.click();
await s.waitForTimeout(600);
for (const [name, sel] of [["gegengelesen", "13 O 730/22"], ["ungeprueft", "305c"]]) {
  const info = await s.evaluate((sel) => {
    const el = [...document.querySelectorAll("button")].find((e) => e.textContent?.includes(sel));
    if (!el) return null;
    el.scrollIntoView({ block: "center" });
    const cls = el.className;
    el.click();
    return { gestrichelt: cls.includes("border-dashed"), chiptext: el.textContent.trim() };
  }, sel);
  await s.waitForTimeout(700);
  const pop = await s.locator("[data-radix-popper-content-wrapper]").first().textContent();
  console.log(`\n[${name}]  Chip: "${info?.chiptext}"  gestrichelter Rahmen: ${info?.gestrichelt}`);
  console.log(`   Popover: ${pop?.replace(/\s+/g, " ").slice(0, 200)}`);
  await s.screenshot({ path: `shots/chip_${name}.png` });
  await s.keyboard.press("Escape");
  await s.waitForTimeout(300);
}
await b.close();
