import { chromium } from "playwright";
const [fall, breite] = [process.argv[2], Number(process.argv[3] || 1440)];
const hoehe = breite === 1920 ? 1080 : 900;
const b = await chromium.launch();
const s = await b.newPage({ viewport: { width: breite, height: hoehe } });
await s.goto(`http://localhost:8080/faelle/${fall}`, { waitUntil: "networkidle" });
console.log(`### ${breite}x${hoehe}`);
for (const schritt of [1, 2, 3, 4, 5, 6]) {
  await s.locator(`nav[aria-label="Schritte"] button`).nth(schritt - 1).click();
  await s.waitForTimeout(400);
  const m = await s.evaluate(() => {
    const sek = document.querySelector('section[aria-label="Dokumente"]');
    const viewer = document.getElementById("dokumentspalte");
    const doc = document.documentElement;
    // waagerechter Überlauf + Elemente, die aus ihrem Kasten laufen
    const ueber = [...document.querySelectorAll("body *")].filter((e) => {
      const r = e.getBoundingClientRect();
      return r.width > 0 && (r.right > doc.clientWidth + 1 || r.left < -1);
    }).length;
    // kleinste tatsächlich gerenderte Schriftgröße im sichtbaren Text
    let min = 99;
    for (const e of document.querySelectorAll("body *")) {
      if (!e.textContent?.trim() || e.children.length) continue;
      const r = e.getBoundingClientRect();
      if (r.width < 1) continue;
      min = Math.min(min, parseFloat(getComputedStyle(e).fontSize));
    }
    return {
      spalte_px: sek ? Math.round(sek.getBoundingClientRect().width) : 0,
      viewer_sichtbar: !!viewer,
      seitenhoehe: doc.scrollHeight,
      ueberlauf: ueber,
      min_schrift: min,
      waagerecht: doc.scrollWidth > doc.clientWidth,
    };
  });
  console.log(
    `S${schritt}  Spalte ${String(m.spalte_px).padStart(4)}px (${(100 * m.spalte_px / breite).toFixed(0)}%)  Viewer:${m.viewer_sichtbar ? "auf" : "zu "}  Seite ${String(m.seitenhoehe).padStart(5)}px  Überlauf ${m.ueberlauf}  h-scroll ${m.waagerecht}  kleinste Schrift ${m.min_schrift}px`,
  );
  if ([3, 4, 5].includes(schritt) && breite === 1440)
    await s.screenshot({ path: `/private/tmp/claude-501/-Users-sunghopark-dev-llt26/2633453b-2faa-4541-9098-a5686ef6e607/scratchpad/s${schritt}.png` });
}
await b.close();
