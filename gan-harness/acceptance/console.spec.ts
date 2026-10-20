/**
 * UI acceptance tests for the Asteria flight console.
 *
 *   BASE_URL=http://127.0.0.1:3000 API_URL=http://127.0.0.1:8000 \
 *     npx playwright test -c gan-harness/acceptance
 *
 * Every number checked on screen is compared to the API, never to a constant.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const API_URL = (process.env.API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const fmtM = (v: number) => new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(v);

async function getJson<T>(request: APIRequestContext, path: string): Promise<T> {
  const r = await request.get(`${API_URL}${path}`);
  expect(r.ok(), `${path} -> ${r.status()}`).toBeTruthy();
  return (await r.json()) as T;
}

type Fleet = {
  flights: { id: string; name: string; apogee: { real_m: number; ghost_m: number } }[];
  provenance: { commit: string };
};

// 9 ------------------------------------------------------------------------
test("console loads the real fleet with provenance and no sample data", async ({ page, request }) => {
  const fleet = await getJson<Fleet>(request, "/api/rockets/fleet");
  await page.goto("/");
  const picker = page.getByRole("combobox", { name: "Flight" });
  await expect(picker).toBeVisible();
  await expect(picker.locator("option")).toHaveCount(fleet.flights.length);
  await expect(page.getByTestId("provenance-chip")).toContainText(fleet.provenance.commit.slice(0, 7));
  await expect(page.getByText(/sample data/i)).toHaveCount(0);
});

// 10 -----------------------------------------------------------------------
test("selecting a flight shows its Ghost / Real / Δ from the API", async ({ page, request }) => {
  const fleet = await getJson<Fleet>(request, "/api/rockets/fleet");
  const target = fleet.flights[1];
  await page.goto("/");
  await page.getByRole("combobox", { name: "Flight" }).selectOption(target.id);
  await expect(page.getByTestId("mission-name")).toHaveText(target.name);
  const table = page.getByRole("table", { name: "Vehicle state" });
  for (const col of ["Ghost", "Real", "Δ"]) {
    await expect(table.getByRole("columnheader", { name: col })).toBeVisible();
  }
  await expect(page.getByTestId("apogee-real")).toHaveText(fmtM(target.apogee.real_m));
  await expect(page.getByTestId("apogee-ghost")).toHaveText(fmtM(target.apogee.ghost_m));
});

// 11 -----------------------------------------------------------------------
test("correction toggle switches between pure physics and held-out correction", async ({ page }) => {
  await page.goto("/");
  const state = page.getByTestId("correction-state");
  const before = (await state.textContent())?.trim();
  await page.getByRole("button", { name: /pure physics|apply learned correction/i }).click();
  await expect(state).not.toHaveText(before ?? "");
  await expect(page.getByTestId("residual-label")).toContainText(/physics only|held-out correction/i);
});

// 12 -----------------------------------------------------------------------
test("gap map, next best flight, 3D view and gated orbits are honest", async ({ page, request }) => {
  const nb = await getJson<{ target: { mach: [number, number] } }>(request, "/api/rockets/nextbest");
  await page.goto("/");
  const gap = page.getByRole("img", { name: /reality gap map/i });
  await expect(gap).toBeVisible();
  await expect(gap.locator('[data-charted="false"]').first()).toBeAttached();
  await expect(page.getByTestId("nextbest-mach")).toContainText(nb.target.mach[0].toFixed(1));
  await expect(page.getByTestId("globe").locator("canvas").first()).toBeAttached({ timeout: 20_000 });

  const orbits = await getJson<{ available: boolean }>(request, "/api/orbits/status");
  await page.getByRole("tab", { name: /orbits/i }).click();
  if (!orbits.available) {
    await expect(page.getByTestId("orbits-gated")).toContainText(/space-track/i);
  } else {
    await expect(page.getByRole("table", { name: "Orbit state" })).toBeVisible();
  }
});
