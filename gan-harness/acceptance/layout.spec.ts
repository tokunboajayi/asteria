import { expect, test, type Page } from "@playwright/test";

/**
 * Layout acceptance: the console must stay readable at every common screen size.
 *
 * Measured from the rendered page, not judged by eye:
 *  - no two visible pieces of text overlap (HTML and SVG chart text alike),
 *  - no sideways page scroll,
 *  - the 3D view keeps a usable height,
 *  - no text smaller than 11px.
 *
 * Text drawn inside the Cesium canvas (ruler labels) is not in the DOM and is
 * checked by screenshot review instead.
 */

const SIZES = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "laptop", width: 1280, height: 720 },
  // 1888 px screen at 150% display scaling: three columns just fit.
  { name: "scaled laptop", width: 1258, height: 670 },
  { name: "small laptop", width: 1024, height: 768 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "phone", width: 390, height: 844 },
] as const;

const MIN_FONT_PX = 11;
// Must match the breakpoint in web/src/components/Console.module.css.
const CONSOLE_MODE_MIN_WIDTH = 1184;
const MIN_GLOBE_PX = 280;
// Boxes may touch or graze; anything beyond this many pixels in both directions is an overlap.
const TOLERANCE_PX = 1;

interface TextBox {
  text: string;
  owner: string;
  x: number;
  y: number;
  w: number;
  h: number;
  fontPx: number;
}

/** Every visible text run on the page, clipped to the scroll areas that contain it. */
async function textBoxes(page: Page): Promise<TextBox[]> {
  return page.evaluate(() => {
    const describe = (el: Element) => {
      const id = el.getAttribute("data-testid");
      const cls = typeof el.className === "string" ? el.className.split(" ")[0] : "";
      return `${el.tagName.toLowerCase()}${id ? `[${id}]` : ""}${cls ? `.${cls}` : ""}`;
    };
    // The browser's own test: also false inside collapsed <details> and closed popovers.
    const visible = (el: Element) =>
      el.checkVisibility({ opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true });
    /** The part of `r` left after clipping by every scrolling/clipping ancestor and the viewport. */
    const clip = (el: Element, r: DOMRect) => {
      let x0 = r.left;
      let y0 = r.top;
      let x1 = r.right;
      let y1 = r.bottom;
      for (let e: Element | null = el.parentElement; e; e = e.parentElement) {
        const s = getComputedStyle(e);
        if (/(auto|scroll|hidden|clip)/.test(s.overflowX + s.overflowY)) {
          const c = e.getBoundingClientRect();
          x0 = Math.max(x0, c.left);
          y0 = Math.max(y0, c.top);
          x1 = Math.min(x1, c.right);
          y1 = Math.min(y1, c.bottom);
        }
      }
      x0 = Math.max(x0, 0);
      y0 = Math.max(y0, 0);
      x1 = Math.min(x1, window.innerWidth);
      y1 = Math.min(y1, document.documentElement.scrollHeight);
      return x1 > x0 && y1 > y0 ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : null;
    };
    const out: TextBox[] = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const text = (n.textContent ?? "").trim();
      const owner = n.parentElement;
      if (!text || !owner || owner.closest("script,style,noscript,.cesium-widget")) continue;
      // Screen-reader-only text is clipped to nothing on purpose.
      if (!visible(owner) || owner.closest(".visually-hidden")) continue;
      const range = document.createRange();
      range.selectNodeContents(n);
      // One box per line, so wrapped text is measured as it is drawn.
      for (const r of Array.from(range.getClientRects())) {
        if (r.width < 1 || r.height < 1) continue;
        const box = clip(owner, r);
        if (!box) continue;
        out.push({
          text: text.slice(0, 40),
          owner: describe(owner),
          ...box,
          // Page coordinates, so tall (phone) pages compare correctly.
          y: box.y + window.scrollY,
          fontPx: parseFloat(getComputedStyle(owner).fontSize),
        });
      }
    }
    return out;
  });
}

function overlaps(boxes: TextBox[]): string[] {
  const found: string[] = [];
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i];
      const b = boxes[j];
      const dx = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      const dy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      if (dx > TOLERANCE_PX && dy > TOLERANCE_PX) {
        found.push(`"${a.text}" (${a.owner}) overlaps "${b.text}" (${b.owner})`);
      }
    }
  }
  return found;
}

async function openConsole(page: Page, flight?: string) {
  await page.goto("/");
  await expect(page.getByTestId("apogee-real")).toBeVisible({ timeout: 20_000 });
  if (flight) {
    await page.getByRole("combobox", { name: "Flight" }).selectOption(flight);
    await expect(page.getByTestId("mission-name")).not.toHaveText("", { timeout: 20_000 });
  }
  await page.waitForTimeout(1500); // charts and globe overlays settle
}

for (const size of SIZES) {
  test(`readable layout at ${size.name} ${size.width}×${size.height}`, async ({ page }) => {
    await page.setViewportSize({ width: size.width, height: size.height });
    await openConsole(page);

    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect.soft(scrollWidth, "no sideways page scroll").toBeLessThanOrEqual(size.width);

    if (size.width >= CONSOLE_MODE_MIN_WIDTH) {
      // Columns side by side: each scrolls on its own and the page itself never does,
      // so no column can end early and leave empty space beside a longer one.
      const pageHeight = await page.evaluate(() => document.documentElement.scrollHeight);
      expect.soft(pageHeight, "page does not scroll; columns scroll on their own").toBeLessThanOrEqual(size.height);
    }

    const globe = await page.getByTestId("globe").boundingBox();
    expect.soft(globe?.height ?? 0, "3D view keeps a usable height").toBeGreaterThanOrEqual(MIN_GLOBE_PX);

    const boxes = await textBoxes(page);
    const tiny = [...new Set(boxes.filter((b) => b.fontPx < MIN_FONT_PX).map((b) => `${b.owner} ${b.fontPx}px`))];
    expect.soft(tiny, `no text under ${MIN_FONT_PX}px`).toEqual([]);
    expect.soft(overlaps(boxes), "no overlapping text").toEqual([]);
  });
}

test("no overlapping text with GNSS track and correction applied", async ({ page }) => {
  await openConsole(page, "prometheus-2022");
  await page.getByRole("button", { name: /apply learned correction/i }).click();
  await page.waitForTimeout(800);
  expect(overlaps(await textBoxes(page)), "no overlapping text").toEqual([]);
});

// By name, not position: inserting a size into SIZES must not change what this test covers.
const REPLAY_SIZES = SIZES.filter((s) => s.name === "laptop" || s.name === "phone");

for (const size of REPLAY_SIZES) {
  test(`mission replay HUD fits at ${size.name} ${size.width}×${size.height}`, async ({ page }) => {
    await page.setViewportSize({ width: size.width, height: size.height });
    await openConsole(page, "prometheus-2022");
    await page.getByTestId("mission-replay").click();
    await expect(page.getByTestId("replay-hud")).toBeVisible();
    await page.waitForTimeout(4000); // into the burn: a callout is up
    await expect(page.getByTestId("replay-hud")).toContainText(/Boost|Coast/);
    expect(overlaps(await textBoxes(page)), "no overlapping text during replay").toEqual([]);
    await page.getByTestId("mission-replay").click();
    await expect(page.getByTestId("replay-hud")).toHaveCount(0);
  });
}

// Orbits tab: only when orbit artifacts exist (they need a Space-Track login).
const ORBIT_SIZES = SIZES.filter((s) => s.name === "desktop" || s.name === "laptop" || s.name === "phone");

for (const size of ORBIT_SIZES) {
  test(`orbits tab readable at ${size.name} ${size.width}×${size.height}`, async ({ page, request }) => {
    const api = process.env.API_URL ?? "http://127.0.0.1:8000";
    const status = await (await request.get(`${api}/api/orbits/status`)).json();
    test.skip(!status.available, "orbit artifacts not built");
    await page.setViewportSize({ width: size.width, height: size.height });
    await openConsole(page);
    await page.getByRole("tab", { name: /orbits/i }).click();
    await expect(page.getByTestId("orbit-globe")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("density-plot")).toBeVisible();
    await page.waitForTimeout(1500);

    const globe = await page.getByTestId("orbit-globe").boundingBox();
    expect.soft(globe?.height ?? 0, "orbit view keeps a usable height").toBeGreaterThanOrEqual(MIN_GLOBE_PX);
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect.soft(scrollWidth, "no sideways page scroll").toBeLessThanOrEqual(size.width);
    const boxes = await textBoxes(page);
    const tiny = [...new Set(boxes.filter((b) => b.fontPx < MIN_FONT_PX).map((b) => `${b.owner} ${b.fontPx}px`))];
    expect.soft(tiny, `no text under ${MIN_FONT_PX}px`).toEqual([]);
    expect.soft(overlaps(boxes), "no overlapping text").toEqual([]);

    await page.getByRole("button", { name: /CCSDS OEM/ }).first().click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(page.getByTestId("oem-download")).toHaveAttribute("href", /\/api\/export\/oem\/orbit\/\d+$/);
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  });
}
