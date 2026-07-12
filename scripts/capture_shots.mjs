import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';

const base = 'http://localhost:8098/index.html';
const outDir = process.argv[2] || '.';
const browser = await chromium.launch({
  executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist', '--no-sandbox'],
});
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
const errs = [];
page.on('pageerror', e => errs.push(e.message));
await page.goto(base, { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForFunction(() => !!window.__akina, { timeout: 15000 });
await page.waitForTimeout(500);

const bbox = await page.evaluate(() => window.__akina.bbox());
const [cxx, cyy, czz] = bbox.center;
const spanX = bbox.size[0], spanZ = bbox.size[2];
const reach = Math.max(spanX, spanZ);

// helper: point on centerline
const at = i => page.evaluate(k => window.__akina.centers[k].toArray(), i);

async function shot(name, camPos, target, opts = {}) {
  await page.evaluate(f => { window.__akina.scene.fog.far = f; }, opts.fog ?? 900);
  await page.evaluate(([c, t]) => window.__akina.look(c, t), [camPos, target]);
  await page.evaluate(() => window.__akina.drive(false));
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${outDir}/${name}.png` });
  const hud = await page.evaluate(() => document.querySelector('#sector').textContent);
  console.log(name.padEnd(22), '->', hud);
}

// 1. Aerial overview of the whole course (fog pushed back so all 2.6 km shows)
await shot('01_overview',
  [cxx - 700, cyy + 1900, czz + 1500],
  [cxx, cyy - 120, czz], { fog: 6000 });

// 1b. Angled aerial from the start end
await shot('01b_aerial_angled',
  [cxx + 700, cyy + 1100, czz + 2100],
  [cxx - 100, cyy - 80, czz], { fog: 6000 });

// 2. Start / Lake Akina
{
  const p = await at(4);
  await shot('02_start_lake', [p[0] + 120, p[1] + 70, p[2] + 130], [p[0] - 60, p[1] - 10, p[2] - 60]);
}

// 3. Five hairpins from above (switchbacks)
{
  const p = await at(300);
  await shot('03_hairpins_top', [p[0] + 40, p[1] + 150, p[2] + 60], [p[0], p[1] - 40, p[2]]);
}

// 4. Chase behind the car in the hairpins
{
  await page.evaluate(() => window.__akina.setT(315));
  const car = await page.evaluate(() => window.__akina.car.position.toArray());
  const tan = await page.evaluate(() => window.__akina.tangents[315].toArray());
  await shot('04_hairpin_chase',
    [car[0] - tan[0] * 13 + 3, car[1] + 6, car[2] - tan[2] * 13],
    car);
}

// 5. Low, on-road dramatic angle near the car (gutter side)
{
  await page.evaluate(() => window.__akina.setT(305));
  const car = await page.evaluate(() => window.__akina.car.position.toArray());
  const r = await page.evaluate(() => window.__akina.rights[305].toArray());
  await shot('05_car_lowangle',
    [car[0] + r[0] * 9, car[1] + 2.2, car[2] + r[2] * 9],
    car);
}

// 6. High-speed section (sweepers)
{
  const p = await at(620);
  await shot('06_highspeed', [p[0] + 70, p[1] + 55, p[2] + 90], [p[0] - 40, p[1] - 20, p[2] - 40]);
}

// 7. Final descent to the base
{
  const p = await at(840);
  await shot('07_final_descent', [p[0] + 90, p[1] + 70, p[2] + 90], [p[0] - 30, p[1] - 30, p[2] - 30]);
}

// 8. Front 3/4 of the car
{
  await page.evaluate(() => window.__akina.setT(160));
  const car = await page.evaluate(() => window.__akina.car.position.toArray());
  const tan = await page.evaluate(() => window.__akina.tangents[160].toArray());
  const r = await page.evaluate(() => window.__akina.rights[160].toArray());
  await shot('08_car_front34',
    [car[0] + tan[0] * 9 + r[0] * 5, car[1] + 3, car[2] + tan[2] * 9 + r[2] * 5],
    car);
}

console.log('errors:', errs.length ? errs.join('\n') : 'none');
await browser.close();
