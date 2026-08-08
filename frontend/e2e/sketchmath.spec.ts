import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
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

const dispatchCanvasViewBoxPoint = async (page: Page, x: number, y: number) => {
  await page.getByTestId("sketchmath-canvas").evaluate((element, coords) => {
    const svg = element as SVGSVGElement;
    const svgBox = svg.getBoundingClientRect();
    const viewBox = svg.viewBox.baseVal;
    const scale = Math.min(svgBox.width / viewBox.width, svgBox.height / viewBox.height);
    const contentLeft = svgBox.left + (svgBox.width - viewBox.width * scale) / 2;
    const contentTop = svgBox.top + (svgBox.height - viewBox.height * scale) / 2;
    svg.dispatchEvent(new MouseEvent("click", {
      bubbles: true,
      clientX: contentLeft + (coords.x - viewBox.x) * scale,
      clientY: contentTop + (coords.y - viewBox.y) * scale,
    }));
  }, { x, y });
};

const dragSvgEntityToViewBoxPoint = async (page: Page, target: string | Locator, x: number, y: number) => {
  const entity = typeof target === "string" ? page.locator(target) : target;
  const coordinates = await page.getByTestId("sketchmath-canvas").evaluate((element, coords) => {
    const svg = element as SVGSVGElement;
    const svgBox = svg.getBoundingClientRect();
    const viewBox = svg.viewBox.baseVal;
    const scale = Math.min(svgBox.width / viewBox.width, svgBox.height / viewBox.height);
    const contentLeft = svgBox.left + (svgBox.width - viewBox.width * scale) / 2;
    const contentTop = svgBox.top + (svgBox.height - viewBox.height * scale) / 2;
    return {
      x: contentLeft + (coords.x - viewBox.x) * scale,
      y: contentTop + (coords.y - viewBox.y) * scale,
    };
  }, { x, y });
  const source = await entity.boundingBox();
  if (!source) throw new Error("Unable to locate draggable SVG entity");
  await page.mouse.move(source.x + source.width / 2, source.y + source.height / 2);
  await page.mouse.down();
  await page.mouse.move(coordinates.x, coordinates.y, { steps: 4 });
  await page.mouse.up();
};

const shiftClickEntity = async (page: Page, selector: string) => {
  await page.locator(selector).last().dispatchEvent("click", { shiftKey: true });
};

const selectFirstTwoLines = async (page: Page) => {
  await clickSvgPrimitiveCenter(page, '[data-testid^="entity-line_"] line.sketchmath-line', { first: true });
  await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 1 line");
  await clickSvgPrimitiveCenter(page, '[data-testid^="entity-line_"] line.sketchmath-line', { shift: true });
  await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 2 lines");
};

const makePointsCoincident = async (page: Page, firstIndex: number, secondIndex: number) => {
  const points = page.locator('[data-entity-type="point_2d"]');
  await points.nth(firstIndex).dispatchEvent("click");
  await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 1 point");
  await points.nth(secondIndex).dispatchEvent("click", { shiftKey: true });
  await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 2 points");
  await clickWorkbenchButton(page, "Coincident");
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
    await expect(page.getByTestId("sketchmath-status")).toContainText("Under-constrained");
    await expect(page.getByTestId("sketchmath-solver-status-detail")).toContainText("can still move");
    await expect(page.getByText(/Independent equations:/)).toHaveCount(0);

    await clickWorkbenchButton(page, "Apply length");
    await expect(page.getByTestId("sketchmath-selected-constraints")).toContainText("distance 17.5 mm");
    await expect(page.getByTestId("sketchmath-workbench-panel").getByTestId("sketchmath-status")).toContainText("Partially analyzed");

    await page.getByRole("button", { name: "Line" }).first().click();
    await page.getByTestId("sketchmath-canvas").click({ position: { x: 180, y: 260 } });
    await page.getByTestId("sketchmath-canvas").click({ position: { x: 420, y: 260 } });

    await expect(page.locator('[data-testid^="entity-line_"]').nth(1)).toBeAttached();
    await expect(page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Extrude" })).toBeDisabled();

    await page.getByRole("button", { name: "Select" }).click();
    await clickSvgPrimitiveCenter(page, '[data-testid^="entity-line_"] line.sketchmath-line', { shift: true, first: true });
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 2 lines");
    await clickWorkbenchButton(page, "Parallel");
    await expect(page.getByTestId("sketchmath-selected-constraints")).toContainText("Parallel");
    await clickWorkbenchButton(page, "Undo");
    await selectFirstTwoLines(page);
    await clickWorkbenchButton(page, "Perpendicular");
    await expect(page.getByTestId("sketchmath-selected-constraints")).toContainText("Perpendicular");
    await clickWorkbenchButton(page, "Undo");
    await selectFirstTwoLines(page);
    await clickWorkbenchButton(page, "Equal Length");
    await expect(page.getByTestId("sketchmath-selected-constraints")).toContainText("Equal length");

    await clickWorkbenchButton(page, "Show Advanced / Debug");
    await expect(page.getByTestId("sketchmath-solver-analysis-debug")).toContainText("Coverage: partial");
    await expect(page.getByTestId("sketchmath-solver-analysis-debug")).toContainText("Independent equations:");
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
    await expect(page.getByTestId("sketchmath-workbench-panel").getByTestId("sketchmath-status")).toContainText("Partially analyzed");
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
    await expect(page.getByTestId("sketchmath-workbench-panel").getByTestId("sketchmath-status")).toContainText("Partially analyzed");

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
    const holeCenterX = page.getByLabel("Selected hole center X");
    const holeCenterY = page.getByLabel("Selected hole center Y");
    const shiftedX = Number(await holeCenterX.inputValue()) + 2;
    await page.getByLabel("Selected hole diameter").fill("6");
    await holeCenterX.fill(String(shiftedX));
    await holeCenterY.fill(await holeCenterY.inputValue());
    await page.getByRole("button", { name: "Apply hole update" }).click();
    await expect(page.getByTestId("selected-hole-editor-message")).toContainText("Hole updated");
    await page.screenshot({ path: screenshotPath("sketchmath-hole-placed-committed.png"), fullPage: true });

    await expect(createFeatureButton).toBeEnabled();
    await expect(page.getByTestId("sketchmath-command-panel")).toHaveCount(0);
    await expect(page.getByLabel("Extrusion depth")).toHaveValue("10");
    await createFeatureButton.click();
    await expect(page.getByTestId("sketchmath-cad-feature-summary")).toContainText("Extrude preview ready: profile accepted with 1 hole");
    await expect(page.getByTestId("sketchmath-preview-controls")).toBeVisible();
    const cameraHud = page.getByTestId("sketchmath-solid-camera-hud");
    const initialCamera = await cameraHud.textContent();
    await page.getByTestId("sketchmath-solid-preview-canvas").dragTo(page.getByTestId("sketchmath-solid-preview-canvas"), {
      sourcePosition: { x: 240, y: 180 },
      targetPosition: { x: 310, y: 220 },
      force: true,
    });
    await expect.poll(async () => await cameraHud.textContent()).not.toBe(initialCamera);
    await page.getByRole("button", { name: "Commit Preview" }).click();
    await expect(page.getByTestId("sketchmath-cad-feature-summary")).toContainText("STEP export ready");
    const downloadLink = page.getByRole("link", { name: "Download STEP" });
    await expect(downloadLink).toBeVisible();
    const downloadPromise = page.waitForEvent("download");
    await downloadLink.click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("export.step");
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
    await expect(page.getByTestId("sketchmath-tool-mode")).toContainText("Select");
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

  test("detects and extrudes a profile built from four independent lines", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Line" }).first().click();
    const segments = [
      [[120, 100], [260, 100]],
      [[260, 100], [260, 200]],
      [[260, 200], [120, 200]],
      [[120, 200], [120, 100]],
    ] as const;
    for (const [index, [start, end]] of segments.entries()) {
      await dispatchCanvasViewBoxPoint(page, start[0], start[1]);
      await dispatchCanvasViewBoxPoint(page, end[0], end[1]);
      await expect(page.locator('[data-testid^="entity-line_"]')).toHaveCount(index + 1);
    }
    await page.getByRole("button", { name: "Select" }).click();
    await makePointsCoincident(page, 1, 2);
    await makePointsCoincident(page, 3, 4);
    await makePointsCoincident(page, 5, 6);
    await makePointsCoincident(page, 7, 0);

    const candidates = page.getByTestId("sketchmath-profile-candidates");
    await expect(candidates).toContainText("Valid closed loop", { timeout: 20000 });
    await candidates.getByRole("button", { name: "Create profile" }).click();
    const profile = page.locator('[data-entity-type="profile_2d"]').last();
    await expect(profile).toBeAttached();
    await profile.dispatchEvent("click");
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");

    await clickWorkbenchButton(page, "Extrude");
    await expect(page.getByTestId("sketchmath-cad-feature-summary")).toContainText("Extrude preview ready");
    await page.getByRole("button", { name: "Commit Preview" }).click();
    await expect(page.getByRole("link", { name: "Download STEP" })).toBeVisible();
    await page.screenshot({ path: screenshotPath("sketchmath-detected-line-profile-step.png"), fullPage: true });
  });

  test("preserves horizontal, vertical, and coincident constraints during endpoint dragging", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Line" }).first().click();
    await dispatchCanvasViewBoxPoint(page, 120, 120);
    await dispatchCanvasViewBoxPoint(page, 260, 150);
    await expect(page.locator('[data-testid^="entity-line_"]')).toHaveCount(1);
    await clickWorkbenchButton(page, "Horizontal");

    const points = page.locator('[data-entity-type="point_2d"]');
    await dragSvgEntityToViewBoxPoint(page, points.nth(1), 280, 190);
    const firstLine = page.locator('[data-testid^="entity-line_"]').nth(0).locator("line.sketchmath-line");
    await expect.poll(async () => await firstLine.getAttribute("y1") === await firstLine.getAttribute("y2")).toBe(true);

    await page.getByRole("button", { name: "Line" }).first().click();
    await dispatchCanvasViewBoxPoint(page, 340, 100);
    await dispatchCanvasViewBoxPoint(page, 370, 220);
    await expect(page.locator('[data-testid^="entity-line_"]')).toHaveCount(2);
    await page.getByRole("button", { name: "Select" }).click();
    await clickSvgPrimitiveCenter(page, '[data-testid^="entity-line_"] line.sketchmath-line');
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 1 line");
    await clickWorkbenchButton(page, "Vertical");
    await dragSvgEntityToViewBoxPoint(page, points.nth(3), 410, 240);
    const secondLine = page.locator('[data-testid^="entity-line_"]').nth(1).locator("line.sketchmath-line");
    await expect.poll(async () => await secondLine.getAttribute("x1") === await secondLine.getAttribute("x2")).toBe(true);

    await page.getByRole("button", { name: "Select" }).click();
    await points.nth(1).dispatchEvent("click");
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 1 point");
    await points.nth(2).dispatchEvent("click", { shiftKey: true });
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 2 points");
    await clickWorkbenchButton(page, "Coincident");
    await dragSvgEntityToViewBoxPoint(page, points.nth(1), 300, 160);
    await expect.poll(async () => {
      const first = points.nth(1);
      const second = points.nth(2);
      return await first.getAttribute("cx") === await second.getAttribute("cx") && await first.getAttribute("cy") === await second.getAttribute("cy");
    }).toBe(true);
    await page.screenshot({ path: screenshotPath("sketchmath-foundational-constrained-drag.png"), fullPage: true });
  });

  test("draws, edits, and extrudes a standalone circle", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Circle" }).click();
    await clickSvgViewBoxPoint(page, 220, 160);
    await clickSvgViewBoxPoint(page, 260, 160);

    const circle = page.locator('[data-entity-type="circle_2d"]').last();
    await expect(circle).toBeVisible();
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Circle");
    await page.getByLabel("Circle radius").fill("30");
    await clickWorkbenchButton(page, "Apply radius");
    await expect(page.getByLabel("Circle radius")).toHaveValue("30");
    await expect(circle).toHaveAttribute("r", "30");

    await clickWorkbenchButton(page, "Extrude");
    await expect(page.getByTestId("sketchmath-cad-feature-summary")).toContainText("Extrude preview ready");
    await page.getByRole("button", { name: "Commit Preview" }).click();
    await expect(page.getByRole("link", { name: "Download STEP" })).toBeVisible();
    await page.screenshot({ path: screenshotPath("sketchmath-circle-profile-step.png"), fullPage: true });
  });

  test("keeps multi-step undo and redo backend-authoritative across a branch edit", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Line" }).first().click();
    await clickSvgViewBoxPoint(page, 120, 120);
    await clickSvgViewBoxPoint(page, 260, 120);
    await clickWorkbenchButton(page, "Apply length");
    await clickWorkbenchButton(page, "Horizontal");
    await page.getByRole("button", { name: "Circle" }).click();
    await clickSvgViewBoxPoint(page, 320, 180);
    await clickSvgViewBoxPoint(page, 350, 180);
    await expect(page.locator('[data-entity-type="circle_2d"]')).toHaveCount(1);

    const undo = page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Undo" });
    const redo = page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Redo" });
    for (let index = 0; index < 4; index += 1) await undo.click();
    await expect(page.locator('[data-entity-type="circle_2d"]')).toHaveCount(0);
    await expect(page.locator('[data-testid^="entity-line_"]')).toHaveCount(0);
    for (let index = 0; index < 4; index += 1) await redo.click();
    await expect(page.locator('[data-entity-type="circle_2d"]')).toHaveCount(1);
    await expect(page.locator('[data-testid^="entity-line_"]')).toHaveCount(1);

    await undo.click();
    await undo.click();
    await page.getByRole("button", { name: "Point" }).click();
    await clickSvgViewBoxPoint(page, 380, 220);
    await expect(redo).toBeDisabled();

    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();
    const snapshot = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    expect(snapshot.ok()).toBeTruthy();
    const state = await snapshot.json() as { can_redo: boolean; history_length: number; selection_context: { items: unknown[] } };
    expect(state.can_redo).toBe(false);
    expect(state.history_length).toBe(3);
    expect(state.selection_context.items).toHaveLength(4);
    await page.screenshot({ path: screenshotPath("sketchmath-history-branch.png"), fullPage: true });
  });
});
