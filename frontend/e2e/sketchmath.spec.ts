import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { openSketchMath } from "./helpers/sketchmath";

const screenshotPath = (name: string) => `../tmp/sketchmath_sol/${name}`;

const clickWorkbenchButton = async (page: Page, label: string) => {
  await page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: label }).click();
};

const clickSvgPrimitiveCenter = async (page: Page, selector: string, options: { shift?: boolean; first?: boolean } = {}) => {
  const matches = page.locator(selector);
  const primitive = options.first ? matches.first() : matches.last();
  await primitive.scrollIntoViewIfNeeded();
  const point = await primitive.evaluate((element) => {
    const primitive = element as SVGGraphicsElement;
    const svg = primitive.ownerSVGElement;
    if (!svg) {
      throw new Error("SVG owner not found");
    }
    const primitiveBox = primitive.getBBox();
    const svgBox = svg.getBoundingClientRect();
    const viewBox = svg.viewBox.baseVal;
    const scale = Math.min(svgBox.width / viewBox.width, svgBox.height / viewBox.height);
    const contentWidth = viewBox.width * scale;
    const contentHeight = viewBox.height * scale;
    const contentLeft = svgBox.left + (svgBox.width - contentWidth) / 2;
    const contentTop = svgBox.top + (svgBox.height - contentHeight) / 2;
    return {
      x: contentLeft + (primitiveBox.x + primitiveBox.width / 2 - viewBox.x) * scale,
      y: contentTop + (primitiveBox.y + primitiveBox.height / 2 - viewBox.y) * scale,
    };
  });
  if (options.shift) {
    await page.keyboard.down("Shift");
  }
  await page.mouse.click(point.x, point.y);
  if (options.shift) {
    await page.keyboard.up("Shift");
  }
};

const clickSvgViewBoxPoint = async (page: Page, x: number, y: number) => {
  const point = await page.getByTestId("sketchmath-canvas").evaluate((element, coords) => {
    const svg = element as SVGSVGElement;
    const svgBox = svg.getBoundingClientRect();
    const viewBox = svg.viewBox.baseVal;
    const scale = Math.min(svgBox.width / viewBox.width, svgBox.height / viewBox.height);
    const contentWidth = viewBox.width * scale;
    const contentHeight = viewBox.height * scale;
    const contentLeft = svgBox.left + (svgBox.width - contentWidth) / 2;
    const contentTop = svgBox.top + (svgBox.height - contentHeight) / 2;
    return {
      x: contentLeft + (coords.x - viewBox.x) * scale,
      y: contentTop + (coords.y - viewBox.y) * scale,
    };
  }, { x, y });
  await page.mouse.click(point.x, point.y);
};

const shiftClickEntity = async (page: Page, selector: string) => {
  await page.locator(selector).last().dispatchEvent("click", { shiftKey: true });
};

test.describe("SketchMath workspace", () => {
  let browserErrors: string[];

  test.beforeEach(({ page }) => {
    browserErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") browserErrors.push(`console: ${message.text()}`);
    });
    page.on("pageerror", (error) => browserErrors.push(`pageerror: ${error.message}`));
  });

  test.afterEach(() => {
    expect(browserErrors).toEqual([]);
  });

  test("loads canvas-first with the sketch toolbar visible and JSON hidden", async ({ page }) => {
    await openSketchMath(page);
    await expect(page.getByTestId("sketchmath-workspace")).toBeVisible();
    await expect(page.getByTestId("sketchmath-canvas")).toBeVisible();
    await expect(page.getByTestId("sketchmath-workbench-panel")).toBeVisible();
    await expect(page.getByRole("button", { name: "Select" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Line" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Circle" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Dimension" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Parallel" })).toHaveCount(0);
    await expect(page.getByTestId("sketchmath-command-panel")).toHaveCount(0);
    await expect(page.getByTestId("sketchmath-command-box")).toHaveCount(0);
    await expect(page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Extrude" })).toBeDisabled();
  });

  test("draws geometry, applies dimensions and constraints, and reveals advanced JSON on demand", async ({ page }) => {
    await openSketchMath(page);

    await page.getByRole("button", { name: "Line" }).first().click();
    await page.getByTestId("sketchmath-canvas").click({ position: { x: 180, y: 180 } });
    await page.getByTestId("sketchmath-canvas").click({ position: { x: 420, y: 180 } });

    await expect(page.locator('[data-testid^="entity-line_"]').first()).toBeAttached();
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 1 line");

    await clickWorkbenchButton(page, "Apply length");
    await expect(page.getByTestId("sketchmath-selected-constraints")).toContainText("distance 17.5 mm");
    await expect(page.getByTestId("sketchmath-workbench-panel").getByTestId("sketchmath-status")).toContainText("Constraints present");

    await page.getByRole("button", { name: "Line" }).first().click();
    await page.getByTestId("sketchmath-canvas").click({ position: { x: 180, y: 260 } });
    await page.getByTestId("sketchmath-canvas").click({ position: { x: 420, y: 260 } });

    await expect(page.locator('[data-testid^="entity-line_"]').nth(1)).toBeAttached();
    await expect(page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Extrude" })).toBeDisabled();

    await page.getByRole("button", { name: "Select" }).click();
    await clickSvgPrimitiveCenter(page, '[data-testid^="entity-line_"] line.sketchmath-line', { shift: true, first: true });
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 2 lines");
    await clickWorkbenchButton(page, "Parallel");
    await expect(page.getByTestId("sketchmath-selected-constraints")).toContainText("parallel_constraint");

    await clickWorkbenchButton(page, "Show Advanced / Debug");
    await page.getByRole("button", { name: "Show Advanced / Debug DSL" }).click();
    await expect(page.getByTestId("sketchmath-command-panel")).toBeVisible();
    await expect(page.getByTestId("sketchmath-command-box")).toBeVisible();
  });

  test("completes the rectangle interaction loop through CAD feature generation", async ({ page }) => {
    await openSketchMath(page);

    const createFeatureButton = page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Extrude" });
    await expect(createFeatureButton).toBeDisabled();
    await expect(page.getByTestId("sketchmath-command-panel")).toHaveCount(0);
    await page.screenshot({ path: screenshotPath("sketchmath-debug-hidden-default.png"), fullPage: true });

    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 140, 120);
    await clickSvgViewBoxPoint(page, 360, 200);
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");
    await expect(page.getByTestId("sketchmath-workbench-panel")).toContainText("Closed profile: valid");
    await expect(page.getByTestId("sketchmath-workbench-panel")).toContainText("Rectangle dimensions");
    await expect(page.getByTestId("sketchmath-workbench-panel").getByTestId("sketchmath-status")).toContainText("Constraints present");
    await expect(page.getByTestId("sketchmath-workbench-panel")).toContainText("Ready for CAD feature");
    await page.screenshot({ path: screenshotPath("sketchmath-rectangle-after-create-selected.png"), fullPage: true });
    await page.getByRole("button", { name: "Dimension" }).first().click();

    const widthLabel = page.locator('[data-testid^="dimension-rect_"][data-testid$="-width"]').last();
    const heightLabel = page.locator('[data-testid^="dimension-rect_"][data-testid$="-height"]').last();

    await clickSvgPrimitiveCenter(page, '[data-testid^="entity-rect_"][data-testid$="_ab"]');
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Rectangle width edge");
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Parent: Rectangle");
    await page.screenshot({ path: screenshotPath("sketchmath-edge-selected-width.png"), fullPage: true });

    await widthLabel.click();
    await expect(page.getByRole("heading", { name: "Edit width dimension" })).toBeVisible();
    await page.getByLabel("Width dimension value").fill("40");
    await page.screenshot({ path: screenshotPath("sketchmath-dimension-edit-width.png"), fullPage: true });
    await page.getByRole("button", { name: "Apply dimension" }).click();
    await expect(widthLabel).toContainText("40 mm", { timeout: 20000 });
    await expect(page.getByTestId("sketchmath-workbench-panel").getByTestId("sketchmath-status")).toContainText("Constraints present");

    await heightLabel.click();
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Rectangle height edge");
    await expect(page.getByRole("heading", { name: "Edit height dimension" })).toBeVisible();
    await page.getByLabel("Height dimension value").fill("25");
    await page.screenshot({ path: screenshotPath("sketchmath-dimension-edit-height.png"), fullPage: true });
    await page.getByRole("button", { name: "Apply dimension" }).click();
    await expect(page.getByTestId("sketchmath-canvas")).toContainText("40 mm", { timeout: 20000 });
    await expect(page.getByTestId("sketchmath-canvas")).toContainText("25 mm", { timeout: 20000 });

    await page.getByLabel("Hole diameter").fill("8");
    await clickWorkbenchButton(page, "Add Hole");
    await expect(page.getByTestId("sketchmath-hole-placement")).toContainText("Click inside selected profile");
    await clickSvgPrimitiveCenter(page, '[data-testid^="rectangle-selection-outline-"]');
    await expect(page.locator('[data-testid^="entity-hole_"]').last()).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId("sketchmath-workbench-panel")).toContainText("Profile holes: 1");
    await page.screenshot({ path: screenshotPath("sketchmath-hole-placed-committed.png"), fullPage: true });

    await expect(createFeatureButton).toBeEnabled();
    await expect(page.getByTestId("sketchmath-command-panel")).toHaveCount(0);
    await expect(page.getByLabel("Extrusion depth")).toHaveValue("10");
    await createFeatureButton.click();
    await expect(page.getByTestId("sketchmath-cad-feature-summary")).toContainText("Extrude preview ready: profile accepted with 1 hole");
    await expect(page.getByTestId("sketchmath-preview-controls")).toBeVisible();
    await page.getByRole("button", { name: "Commit Preview" }).click();
    await expect(page.getByTestId("sketchmath-cad-feature-summary")).toContainText("STEP export ready");
    await expect(page.getByRole("link", { name: "Download STEP" })).toBeVisible();
    await expect(page.getByTestId("sketchmath-command-panel")).toHaveCount(0);
    await page.screenshot({ path: screenshotPath("sketchmath-extrude-normal-ui.png"), fullPage: true });

    await clickWorkbenchButton(page, "Show Advanced / Debug");
    await expect(page.getByTestId("sketchmath-selection-inspector")).toContainText("extrude_profile");
  });

  test("handles referenced rectangle edge delete and clean sketch reset in the normal UI", async ({ page }) => {
    await openSketchMath(page);

    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 160, 140);
    await clickSvgViewBoxPoint(page, 340, 240);
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");
    await expect(page.getByTestId("sketchmath-workbench-panel")).toContainText("Closed profile: valid");

    await page.getByRole("button", { name: "Dimension" }).first().click();
    await clickSvgPrimitiveCenter(page, '[data-testid^="entity-rect_"][data-testid$="_ab"]');
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Rectangle width edge");
    await page.keyboard.press("Delete");
    await expect(page.getByTestId("sketchmath-delete-prompt")).toContainText("This edge belongs to a rectangle");
    await expect(page.getByRole("button", { name: "Delete whole rectangle" })).toBeVisible();
    await expect(page.getByTestId("sketchmath-workspace")).not.toContainText("Cannot delete an entity that is still referenced");
    await page.screenshot({ path: screenshotPath("sketchmath-delete-referenced-edge-safe.png"), fullPage: true });

    await page.getByRole("button", { name: "Delete whole rectangle" }).click();
    await expect(page.locator('[data-testid^="entity-rect_"]')).toHaveCount(0, { timeout: 20000 });
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Nothing");
    await expect(page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Extrude" })).toBeDisabled();

    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 190, 160);
    await clickSvgViewBoxPoint(page, 310, 230);
    await expect(page.locator('[data-testid^="entity-rect_"]')).not.toHaveCount(0);
    await page.getByRole("button", { name: "Clear sketch" }).click();
    await expect(page.locator('[data-testid^="entity-rect_"]')).toHaveCount(0, { timeout: 20000 });
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Nothing");
    await expect(page.getByTestId("sketchmath-workbench-panel")).toContainText("0 points");
    await expect(page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Extrude" })).toBeDisabled();
    await page.screenshot({ path: screenshotPath("sketchmath-clear-sketch-reset.png"), fullPage: true });
  });

  test("supports contextual rectangle selection and multi-line constraints from canvas clicks", async ({ page }) => {
    await openSketchMath(page);

    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 150, 130);
    await clickSvgViewBoxPoint(page, 360, 230);
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");

    await page.getByRole("button", { name: "Dimension" }).first().click();
    await clickSvgPrimitiveCenter(page, '[data-testid^="entity-rect_"][data-testid$="_ab"]');
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Rectangle width edge");
    await page.locator('[data-testid^="dimension-rect_"][data-testid$="-width"]').last().click();
    await page.getByLabel("Width dimension value").fill("40");
    await page.screenshot({ path: screenshotPath("sketchmath-context-width-edge.png"), fullPage: true });
    await page.getByRole("button", { name: "Apply dimension" }).click();
    await expect(page.getByTestId("sketchmath-canvas")).toContainText("40 mm", { timeout: 20000 });

    await clickSvgPrimitiveCenter(page, '[data-testid^="entity-rect_"][data-testid$="_bc"]');
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Rectangle height edge");
    await page.locator('[data-testid^="dimension-rect_"][data-testid$="-height"]').last().click();
    await page.getByLabel("Height dimension value").fill("25");
    await page.getByRole("button", { name: "Apply dimension" }).click();
    await expect(page.getByTestId("sketchmath-canvas")).toContainText("25 mm", { timeout: 20000 });

    await page.keyboard.press("Escape");
    await shiftClickEntity(page, '[data-testid^="entity-rect_"][data-testid$="_ab"]');
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 2 lines");
    await expect(page.getByRole("button", { name: "Parallel" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Perpendicular" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Equal Length" })).toBeEnabled();
    await page.screenshot({ path: screenshotPath("sketchmath-context-two-lines-parallel.png"), fullPage: true });
    await expect(page.getByTestId("sketchmath-workspace")).not.toContainText("Cannot delete an entity that is still referenced");

    await page.getByRole("button", { name: "Clear sketch" }).click();
    await expect(page.locator('[data-testid^="entity-rect_"]')).toHaveCount(0, { timeout: 20000 });
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Nothing");
    await expect(page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Extrude" })).toBeDisabled();
  });
});
