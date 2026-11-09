// Smoke test for index.html before pushing. Usage: node routine/smoke.js [path/to/index.html] [shots-dir]
// Prints "SMOKE OK" or the failed checks (exit code 1).
const path = require("path");
const { chromium } = require("playwright");

(async () => {
  const file = path.resolve(process.argv[2] || "index.html");
  const shots = process.argv[3] || "";
  const data = JSON.parse(require("fs").readFileSync(file, "utf8")
    .split('<script type="application/json" id="radar-data">')[1].split("</script>")[0]);
  const dailyRows = data.L.daily.rows.length;
  const fails = [];
  const browser = await chromium.launch();
  for (const width of [1280, 360]) {
    for (const scheme of ["light", "dark"]) {
      const page = await browser.newPage({ viewport: { width, height: 900 }, colorScheme: scheme });
      const errors = [];
      page.on("pageerror", e => errors.push(e.message));
      await page.goto("file://" + file);
      await page.waitForTimeout(1500);
      const tag = `${width}px ${scheme}`;
      const r = await page.evaluate(() => ({
        rows: document.querySelectorAll(".row").length,
        top3: document.querySelectorAll("#top3List .t3").length,
        take: document.querySelectorAll("#take .tk").length,
        stats: document.querySelectorAll("#stats .stat").length,
        wide: document.documentElement.scrollWidth > window.innerWidth,
        badge: (document.getElementById("langBadge") || {}).textContent,
      }));
      if (r.rows !== dailyRows) fails.push(`${tag}: rows ${r.rows} (expected ${dailyRows})`);
      if (r.top3 !== 3) fails.push(`${tag}: top3 ${r.top3}`);
      if (r.take !== 5) fails.push(`${tag}: signals ${r.take}`);
      if (r.stats !== 4) fails.push(`${tag}: stats ${r.stats}`);
      if (r.wide) fails.push(`${tag}: page wider than the screen`);
      if (r.badge !== "HI") fails.push(`${tag}: language badge is "${r.badge}" (expected HI)`);
      if (shots) await page.screenshot({ path: `${shots}/${width}-${scheme}.png` });
      if (scheme === "light") {
        await page.click("#langBtn");
        await page.waitForTimeout(500);
        const e = await page.evaluate(() => ({
          lang: document.documentElement.getAttribute("lang"),
          take: document.querySelectorAll("#take .tk").length,
          badge: document.getElementById("langBadge").textContent,
        }));
        if (e.lang !== "en" || e.take !== 5 || e.badge !== "EN") fails.push(`${tag}: Simple English switch failed ${JSON.stringify(e)}`);
        await page.click("#themeBtn");
        await page.waitForTimeout(300);
        const dark = await page.evaluate(() => document.getElementById("themeBtn").getAttribute("aria-pressed"));
        if (dark !== "true") fails.push(`${tag}: dark mode button failed`);
        if (shots) await page.screenshot({ path: `${shots}/${width}-switched.png` });
      }
      if (errors.length) fails.push(`${tag}: page errors: ${errors.join(" | ").slice(0, 300)}`);
      await page.close();
    }
  }
  await browser.close();
  if (fails.length) { console.log("SMOKE FAILED:\n - " + fails.join("\n - ")); process.exit(1); }
  console.log("SMOKE OK");
})().catch(e => { console.log("SMOKE FAILED: " + e.message); process.exit(1); });
