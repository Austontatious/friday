import { expect, test } from "@playwright/test";

test.describe("FRIDAY shell", () => {
  test("opens SketchMath from the home screen", async ({ page }) => {
    await page.goto("/");

    await expect(page.locator('[data-friday-shell-ui-version="2026-06-13-sketchmath-theme-tokens-v1"]')).toHaveCount(1);
    await expect(page.getByRole("button", { name: "Althing" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Direct Friday" })).toBeVisible();
    const sketchmathButton = page.getByRole("button", { name: "SketchMath" });
    await expect(sketchmathButton).toBeVisible();

    const title = page.getByText("FRIDAY", { exact: true });
    const composer = page.getByPlaceholder("Ask FRIDAY something...");
    await expect(title).toBeVisible();
    await expect(composer).toBeVisible();

    await expect(title).toHaveCSS("color", "rgb(0, 0, 0)");
    await expect(composer).toHaveCSS("border-top-color", "rgb(0, 0, 0)");

    await sketchmathButton.click();

    await expect(page.getByRole("heading", { name: "SketchMath" })).toBeVisible();

    await page.goto("/");
    await page.getByRole("button", { name: "Toggle color mode" }).click();

    await expect(title).toHaveCSS("color", "rgb(0, 255, 255)");
    await expect(composer).toHaveCSS("border-top-color", "rgb(0, 255, 255)");
    const titleShadow = await title.evaluate((el) => getComputedStyle(el).textShadow);
    expect(titleShadow).toContain("0, 255, 255");
  });
});
