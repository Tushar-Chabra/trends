// Read-only render check before publish. Usage: node routine/render_check.js [index.html]
// Opens every list tab (daily/weekly/monthly/yearly) in Simple English AND Hinglish and flags
// "n/a", "null", "NaN", "undefined", "0%", empty lists or missing charts. Prints RENDER OK or the problems.
const path = require("path");
const { chromium } = require("playwright");
(async () => {
  const file = path.resolve(process.argv[2] || "index.html");
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  await p.goto("file://" + file);
  await p.waitForTimeout(800);
  const fails = [];
  const tabs = await p.$$eval("button.tab", e => e.map(x => x.dataset.k));
  if (tabs.length < 4) fails.push("tabs found: " + tabs.join(","));
  for (const lang of ["EN", "HI"]) {
    if (lang === "HI") { await p.click("#langBtn"); await p.waitForTimeout(400); }
    for (const k of tabs) {
      await p.click("#tab-" + k); await p.waitForTimeout(450);
      const r = await p.evaluate(() => ({
        text: document.body.innerText,
        rows: document.querySelectorAll("#list .row, .row[data-id]").length,
        svgs: document.querySelectorAll("svg").length,
      }));
      const bad = [...r.text.matchAll(/\b(n\/a|null|NaN|undefined)\b|(^|[^\d.])0%/gi)].map(m => m[0].trim());
      if (bad.length) fails.push(`${lang}/${k}: bad text ${JSON.stringify([...new Set(bad)])}`);
      if (r.rows < 1) fails.push(`${lang}/${k}: no repo rows`);
      if (r.svgs < 1) fails.push(`${lang}/${k}: no chart`);
    }
  }
  await b.close();
  if (fails.length) { console.log("RENDER FAILED:\n - " + fails.join("\n - ")); process.exit(1); }
  console.log("RENDER OK (" + tabs.join(", ") + " x EN, HI)");
})();
