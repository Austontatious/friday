import { expect, test } from "@playwright/test";

test.describe("FRIDAY shell", () => {
  test("opens SketchMath from the home screen", async ({ page }) => {
    await page.goto("/");

    await expect(page.locator('[data-friday-shell-ui-version="2026-06-18-command-center-shell-v1"]')).toHaveCount(1);
    await expect(page.getByRole("button", { name: "Althing" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Direct Friday" })).toBeVisible();
    const sketchmathButton = page.getByRole("button", { name: "SketchMath" });
    await expect(sketchmathButton).toBeVisible();

    const title = page.getByRole("heading", { name: "Command Center" });
    const composer = page.getByPlaceholder("Ask FRIDAY something...");
    await expect(title).toBeVisible();
    await expect(composer).toBeVisible();
    await expect(page.getByTestId("friday-telemetry-panel")).toBeVisible();
    await expect(page.getByTestId("friday-session-map")).toBeVisible();

    await expect(composer).toHaveCSS("border-top-color", "rgba(174, 194, 211, 0.24)");
    await page.screenshot({ path: "../docs/runtime/screenshots/friday-command-center-direct.png", fullPage: true });

    await sketchmathButton.click();

    await expect(page.getByRole("heading", { name: "SketchMath" })).toBeVisible();
    await page.screenshot({ path: "../docs/runtime/screenshots/friday-command-center-sketchmath.png", fullPage: true });

    await page.goto("/");
    await page.getByRole("button", { name: "Toggle color mode" }).click();

    await expect(title).toBeVisible();
    await expect(page.getByText("Health")).toBeVisible();
  });
});
