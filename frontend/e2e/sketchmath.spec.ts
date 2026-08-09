import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import { openSketchMath } from "./helpers/sketchmath";

const screenshotPath = (name: string) => `../tmp/sketchmath_sol/${name}`;

const clickWorkbenchButton = async (page: Page, label: string) => {
  await page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: label, exact: true }).click();
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

const dragCanvasViewBoxBox = async (page: Page, start: { x: number; y: number }, end: { x: number; y: number }) => {
  const canvas = page.getByTestId("sketchmath-canvas");
  const points = await canvas.evaluate((element, coords) => {
    const svg = element as SVGSVGElement;
    const svgBox = svg.getBoundingClientRect();
    const viewBox = svg.viewBox.baseVal;
    const scale = Math.min(svgBox.width / viewBox.width, svgBox.height / viewBox.height);
    const contentLeft = svgBox.left + (svgBox.width - viewBox.width * scale) / 2;
    const contentTop = svgBox.top + (svgBox.height - viewBox.height * scale) / 2;
    const mapPoint = (point: { x: number; y: number }) => ({
      x: contentLeft + (point.x - viewBox.x) * scale,
      y: contentTop + (point.y - viewBox.y) * scale,
    });
    return { start: mapPoint(coords.start), end: mapPoint(coords.end) };
  }, { start, end });
  await canvas.dispatchEvent("mousedown", {
    button: 0,
    buttons: 1,
    clientX: points.start.x,
    clientY: points.start.y,
  });
  await expect(page.getByTestId("sketchmath-selection-box")).toHaveCount(1);
  await canvas.dispatchEvent("mousemove", {
    buttons: 1,
    clientX: points.end.x,
    clientY: points.end.y,
  });
  await expect(page.getByTestId("sketchmath-selection-box")).toBeVisible();
  await canvas.dispatchEvent("mouseup", {
    button: 0,
    clientX: points.end.x,
    clientY: points.end.y,
  });
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

const dispatchPointDragToViewBoxPoint = async (target: Locator, x: number, y: number) => {
  await target.evaluate((element, coords) => {
    const entity = element as SVGGraphicsElement;
    const svg = entity.ownerSVGElement;
    if (!svg) throw new Error("SVG owner not found");
    const svgBox = svg.getBoundingClientRect();
    const viewBox = svg.viewBox.baseVal;
    const scale = Math.min(svgBox.width / viewBox.width, svgBox.height / viewBox.height);
    const contentLeft = svgBox.left + (svgBox.width - viewBox.width * scale) / 2;
    const contentTop = svgBox.top + (svgBox.height - viewBox.height * scale) / 2;
    const source = entity.getBoundingClientRect();
    const targetX = contentLeft + (coords.x - viewBox.x) * scale;
    const targetY = contentTop + (coords.y - viewBox.y) * scale;
    entity.dispatchEvent(new MouseEvent("mousedown", {
      bubbles: true,
      button: 0,
      buttons: 1,
      clientX: source.x + source.width / 2,
      clientY: source.y + source.height / 2,
    }));
    svg.dispatchEvent(new MouseEvent("mousemove", { bubbles: true, buttons: 1, clientX: targetX, clientY: targetY }));
    svg.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, button: 0, clientX: targetX, clientY: targetY }));
  }, { x, y });
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
    await expect(page.getByRole("button", { name: "Select", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Line", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Circle" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Region select" })).toBeVisible();
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

    await clickWorkbenchButton(page, "Set horizontal distance");
    await expect(page.getByTestId("sketchmath-selected-constraints")).toContainText("Horizontal distance");
    await expect(page.getByTestId("sketchmath-status")).toContainText("Under-constrained");

    await clickWorkbenchButton(page, "Apply length");
    await expect(page.getByTestId("sketchmath-selected-constraints")).toContainText("distance 17.5 mm");
    await expect(page.getByTestId("sketchmath-workbench-panel").getByTestId("sketchmath-status")).toContainText("Under-constrained");

    await page.getByRole("button", { name: "Line" }).first().click();
    await page.getByTestId("sketchmath-canvas").click({ position: { x: 180, y: 260 } });
    await page.getByTestId("sketchmath-canvas").click({ position: { x: 420, y: 260 } });

    await expect(page.locator('[data-testid^="entity-line_"]').nth(1)).toBeAttached();
    await expect(page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Extrude" })).toBeDisabled();

    await page.getByRole("button", { name: "Select", exact: true }).click();
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
    await expect(page.getByTestId("sketchmath-solver-analysis-debug")).toContainText("Backend: scipy_least_squares_v1");
    await expect(page.getByTestId("sketchmath-solver-analysis-debug")).toContainText("Coverage: exact");
    await expect(page.getByTestId("sketchmath-solver-analysis-debug")).toContainText("Jacobian: scipy_3_point_with_central_rank_check");
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
    await expect(page.getByTestId("sketchmath-workbench-panel").getByTestId("sketchmath-status")).toContainText("Under-constrained");
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
    await expect(page.getByTestId("sketchmath-workbench-panel").getByTestId("sketchmath-status")).toContainText("Under-constrained");

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

  test("commits revisioned extrusion history, edits depth, and preserves stable rebuild identity", async ({ page }) => {
    await openSketchMath(page);
    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();

    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 140, 120);
    await clickSvgViewBoxPoint(page, 360, 200);
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");

    const panel = page.getByTestId("sketchmath-feature-history-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Revision 1");
    await page.getByLabel("Feature extrusion depth").fill("10");
    await panel.getByRole("button", { name: "Add extrusion feature" }).click();
    await expect(panel).toContainText("Revision 2");
    await expect(panel).toContainText("Rebuild passed · 1 feature");
    await expect(panel).toContainText("Volume");

    type FeatureSnapshot = {
      document: {
        revision: number;
        features: Array<{ feature_id: string; parameters: { depth_mm: number } }>;
        last_rebuild: { records: Array<{ feature_id: string; output_signature: string }> };
      };
      feature_history_length: number;
    };
    const firstResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const first = await firstResponse.json() as FeatureSnapshot;
    const featureId = first.document.features[0].feature_id;
    const firstSignature = first.document.last_rebuild.records[0].output_signature;
    expect(first.document.revision).toBe(2);
    expect(first.feature_history_length).toBe(1);

    await page.getByLabel(`Feature depth ${featureId}`).fill("25");
    await panel.getByRole("button", { name: "Apply depth" }).click();
    await expect(panel).toContainText("Revision 3");
    const replacedResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const replaced = await replacedResponse.json() as FeatureSnapshot;
    const replacementSignature = replaced.document.last_rebuild.records[0].output_signature;
    expect(replaced.document.features[0].feature_id).toBe(featureId);
    expect(replaced.document.features[0].parameters.depth_mm).toBe(25);
    expect(replacementSignature).not.toBe(firstSignature);

    await panel.getByRole("button", { name: "Undo feature" }).click();
    await expect(panel).toContainText("Revision 4");
    await expect(page.getByLabel(`Feature depth ${featureId}`)).toHaveValue("10");
    await panel.getByRole("button", { name: "Redo feature" }).click();
    await expect(panel).toContainText("Revision 5");
    await expect(page.getByLabel(`Feature depth ${featureId}`)).toHaveValue("25");

    await page.reload();
    await expect(page.getByText("SketchMath").first()).toBeVisible();
    const reloadedResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const reloaded = await reloadedResponse.json() as FeatureSnapshot;
    expect(reloaded.document.revision).toBe(5);
    expect(reloaded.document.features[0].feature_id).toBe(featureId);
    expect(reloaded.document.last_rebuild.records[0].output_signature).toBe(replacementSignature);
    expect(reloaded.feature_history_length).toBe(2);
    await expect(page.getByTestId(`sketchmath-feature-${featureId}`)).toContainText("succeeded");
  });

  test("creates a center-defined rectangle through the canonical rectangle bundle", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Center rectangle", exact: true }).click();
    await clickSvgViewBoxPoint(page, 260, 180);
    await clickSvgViewBoxPoint(page, 340, 230);

    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");
    const widthBeforeReload = Number(await page.getByLabel("Rectangle width").inputValue());
    const heightBeforeReload = Number(await page.getByLabel("Rectangle height").inputValue());
    expect(Math.abs(widthBeforeReload - 160)).toBeLessThan(3);
    expect(Math.abs(heightBeforeReload - 100)).toBeLessThan(3);
    const rectanglePoints = page.locator('[data-testid^="entity-rect_"][data-entity-type="point_2d"] circle');
    await expect(rectanglePoints).toHaveCount(4);
    const coordinates = await rectanglePoints.evaluateAll((points) => points.map((point) => ({
      x: Number(point.getAttribute("cx")),
      y: Number(point.getAttribute("cy")),
    })));
    expect(Math.abs((Math.min(...coordinates.map((point) => point.x)) + Math.max(...coordinates.map((point) => point.x))) / 2 - 260)).toBeLessThan(2);
    expect(Math.abs((Math.min(...coordinates.map((point) => point.y)) + Math.max(...coordinates.map((point) => point.y))) / 2 - 180)).toBeLessThan(2);
    await expect(page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Extrude" })).toBeEnabled();

    await page.reload();
    await expect(page.getByText("SketchMath").first()).toBeVisible();
    const restoredCoordinates = await page.locator('[data-testid^="entity-rect_"][data-entity-type="point_2d"] circle').evaluateAll((points) => points.map((point) => ({
      x: Number(point.getAttribute("cx")),
      y: Number(point.getAttribute("cy")),
    })));
    expect(restoredCoordinates).toEqual(coordinates);
  });

  test("commits a reload-stable point-backed polyline", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Polyline", exact: true }).click();
    const polylineDraft = page.getByTestId("sketchmath-polyline-draft");
    const draftPointCount = async () => (await polylineDraft.getAttribute("points"))?.trim().split(/\s+/).length;
    await dispatchCanvasViewBoxPoint(page, 140, 120);
    await expect.poll(draftPointCount).toBe(2);
    await dispatchCanvasViewBoxPoint(page, 260, 120);
    await expect.poll(draftPointCount).toBe(3);
    await dispatchCanvasViewBoxPoint(page, 300, 220);
    await expect.poll(draftPointCount).toBe(4);
    await expect(page.getByTestId("sketchmath-polyline-draft")).toBeVisible();
    await clickWorkbenchButton(page, "Finish polyline");

    await expect(page.locator('[data-testid^="entity-polyline_"][data-entity-type="point_2d"]')).toHaveCount(3);
    await expect(page.locator('[data-testid^="entity-polyline_"][data-entity-type="line_2d"]')).toHaveCount(2);
    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    const response = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const snapshot = await response.json() as { selection_context: { items: Array<Record<string, unknown>> } };
    const lines = snapshot.selection_context.items.filter((item) => item.type === "line_2d" && String(item.id).startsWith("polyline_"));
    expect(lines).toHaveLength(2);
    expect(lines[0].end_point_id).toBe(lines[1].start_point_id);

    await page.reload();
    await expect(page.getByText("SketchMath").first()).toBeVisible();
    await expect(page.locator('[data-testid^="entity-polyline_"][data-entity-type="line_2d"]')).toHaveCount(2);
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

  test("detects and extrudes a topology region built from four independent lines", async ({ page }) => {
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
    await page.getByRole("button", { name: "Select", exact: true }).click();
    await makePointsCoincident(page, 1, 2);
    await makePointsCoincident(page, 3, 4);
    await makePointsCoincident(page, 5, 6);
    await makePointsCoincident(page, 7, 0);

    const topologyPanel = page.getByTestId("sketchmath-topology-panel");
    await expect(topologyPanel).toContainText("1 deterministic region detected", { timeout: 20000 });
    await topologyPanel.getByRole("button", { name: "Create region profile 1" }).click();
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

  test("selects a nested region by point, preserves its hole, reports branch diagnostics, and reloads stable references", async ({ page }) => {
    await openSketchMath(page);
    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();

    const line = (name: string, start: [number, number], end: [number, number]) => ({
      version: "0.9",
      command_id: `define_${name}`,
      mode: "commit",
      command_type: "define_line",
      selection: [],
      parameters: { name, start, end },
    });
    const commands = [
      line("outer_bottom", [100, 100], [400, 100]),
      line("outer_right", [400, 100], [400, 400]),
      line("outer_top", [400, 400], [100, 400]),
      line("outer_left", [100, 400], [100, 100]),
      line("inner_bottom", [200, 200], [300, 200]),
      line("inner_right", [300, 200], [300, 300]),
      line("inner_top", [300, 300], [200, 300]),
      line("inner_left", [200, 300], [200, 200]),
      line("outer_branch", [400, 250], [450, 250]),
    ];
    const seeded = await page.request.post(`/api/sketchmath/sessions/${sessionId}/commands/commit`, {
      data: {
        command: {
          version: "0.9",
          command_id: "seed_nested_topology",
          mode: "commit",
          command_type: "batch",
          selection: [],
          parameters: { commands },
        },
      },
    });
    expect(seeded.ok()).toBeTruthy();
    await page.reload();
    await expect(page.getByText("SketchMath").first()).toBeVisible();

    const topologyPanel = page.getByTestId("sketchmath-topology-panel");
    await expect(topologyPanel).toContainText("2 deterministic regions detected", { timeout: 20000 });
    await expect(topologyPanel).toContainText("1 hole");
    await expect(page.getByTestId("sketchmath-topology-diagnostics")).toContainText("t_junction");

    await page.getByRole("button", { name: "Region select" }).click();
    await clickSvgViewBoxPoint(page, 150, 150);
    const selectedButton = page.getByRole("button", { name: "Region selected" });
    await expect(selectedButton).toBeVisible();
    const selectedCard = page.locator('[data-testid^="sketchmath-region-card-"]').filter({ has: selectedButton });
    await expect(selectedCard).toContainText("80000.00 mm²");
    await expect(selectedCard).toContainText("1 hole");
    await expect(page.locator("path.sketchmath-region-selected")).toHaveCount(1);
    const selectedRegionTestId = await selectedCard.getAttribute("data-testid");
    const selectedRegionId = selectedRegionTestId?.replace("sketchmath-region-card-", "");
    expect(selectedRegionId).toBeTruthy();

    await selectedCard.getByRole("button", { name: /Create region profile/ }).click();
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");
    const committed = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    expect(committed.ok()).toBeTruthy();
    const committedState = await committed.json() as {
      history_length: number;
      selection_context: { items: Array<{ id: string; type: string; holes?: string[]; source_region_id?: string | null }> };
    };
    const promoted = committedState.selection_context.items.find(
      (entity) => entity.type === "profile_2d" && entity.source_region_id === selectedRegionId && (entity.holes?.length || 0) === 1,
    );
    expect(promoted).toBeTruthy();
    expect(committedState.history_length).toBe(2);

    await page.reload();
    await expect(page.getByText("SketchMath").first()).toBeVisible();
    const reloaded = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const reloadedState = await reloaded.json() as typeof committedState;
    const restored = reloadedState.selection_context.items.find((entity) => entity.id === promoted?.id);
    expect(restored?.source_region_id).toBe(selectedRegionId);
    expect(restored?.holes).toEqual(promoted?.holes);
    await page.screenshot({ path: screenshotPath("sketchmath-general-topology-nested-region.png"), fullPage: true });
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
    await page.getByRole("button", { name: "Select", exact: true }).click();
    await clickSvgPrimitiveCenter(page, '[data-testid^="entity-line_"] line.sketchmath-line');
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 1 line");
    await clickWorkbenchButton(page, "Vertical");
    await dragSvgEntityToViewBoxPoint(page, points.nth(3), 410, 240);
    const secondLine = page.locator('[data-testid^="entity-line_"]').nth(1).locator("line.sketchmath-line");
    await expect.poll(async () => await secondLine.getAttribute("x1") === await secondLine.getAttribute("x2")).toBe(true);

    await page.getByRole("button", { name: "Select", exact: true }).click();
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
    await expect(page.getByTestId("sketchmath-selected-constraints")).toContainText("Radius");

    await page.getByLabel("Circle diameter").fill("40");
    await clickWorkbenchButton(page, "Apply diameter");
    await expect(page.getByLabel("Circle radius")).toHaveValue("20");
    await expect(circle).toHaveAttribute("r", "20");
    await expect(page.getByTestId("sketchmath-selected-constraints")).toContainText("Diameter");
    await expect(page.getByTestId("sketchmath-selected-constraints")).not.toContainText("Radius •");

    await clickWorkbenchButton(page, "Extrude");
    await expect(page.getByTestId("sketchmath-cad-feature-summary")).toContainText("Extrude preview ready");
    await page.getByRole("button", { name: "Commit Preview" }).click();
    await expect(page.getByRole("link", { name: "Download STEP" })).toBeVisible();
    await page.screenshot({ path: screenshotPath("sketchmath-circle-profile-step.png"), fullPage: true });
  });

  test("creates canonical center and three-point arcs and restores them after reload", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Arc", exact: true }).click();
    await clickSvgViewBoxPoint(page, 200, 180);
    await clickSvgViewBoxPoint(page, 250, 180);
    await expect(page.getByTestId("sketchmath-arc-draft")).toHaveCount(1);
    await clickSvgViewBoxPoint(page, 200, 230);
    await expect(page.locator('[data-entity-type="arc_2d"]')).toHaveCount(1);
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Arc");

    await page.getByRole("button", { name: "3-point arc", exact: true }).click();
    await clickSvgViewBoxPoint(page, 340, 220);
    await clickSvgViewBoxPoint(page, 390, 170);
    await clickSvgViewBoxPoint(page, 440, 220);
    await expect(page.locator('[data-entity-type="arc_2d"]')).toHaveCount(2);
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 3-point arc");
    await expect(page.getByTestId("sketchmath-workbench-panel").getByTestId("sketchmath-status")).toContainText("Under-constrained");

    const pathsBeforeReload = await page.locator('[data-entity-type="arc_2d"] path.sketchmath-line').evaluateAll((paths) =>
      paths.map((path) => path.getAttribute("d")),
    );
    await page.reload();
    await expect(page.getByText("SketchMath").first()).toBeVisible();
    await expect(page.locator('[data-entity-type="arc_2d"]')).toHaveCount(2);
    const pathsAfterReload = await page.locator('[data-entity-type="arc_2d"] path.sketchmath-line').evaluateAll((paths) =>
      paths.map((path) => path.getAttribute("d")),
    );
    expect(pathsAfterReload).toEqual(pathsBeforeReload);
    await page.screenshot({ path: screenshotPath("sketchmath-canonical-arcs.png"), fullPage: true });
  });

  test("fully constrains mixed line, circle, arc, and construction geometry with conflict recovery and reload", async ({ page }) => {
    await openSketchMath(page);

    await page.getByRole("button", { name: "Line" }).first().click();
    await clickSvgViewBoxPoint(page, 140, 140);
    await clickSvgViewBoxPoint(page, 280, 140);
    await page.getByRole("button", { name: "Circle" }).click();
    await clickSvgViewBoxPoint(page, 380, 190);
    await clickSvgViewBoxPoint(page, 410, 190);

    await page.getByRole("button", { name: "Arc", exact: true }).click();
    await dispatchCanvasViewBoxPoint(page, 520, 220);
    await expect(page.getByTestId("sketchmath-canvas-helper")).toContainText("Click the arc start point");
    await dispatchCanvasViewBoxPoint(page, 560, 220);
    await expect(page.getByTestId("sketchmath-canvas-helper")).toContainText("Click the arc end point");
    await dispatchCanvasViewBoxPoint(page, 520, 260);
    await expect(page.locator('[data-entity-type="arc_2d"]')).toHaveCount(1);

    const lineCountBeforeConstruction = await page.locator('[data-testid^="entity-line_"]').count();
    await page.getByRole("button", { name: "Line", exact: true }).click();
    await dispatchCanvasViewBoxPoint(page, 500, 340);
    await expect(page.getByTestId("sketchmath-canvas-helper")).toContainText("Click the line end point");
    await dispatchCanvasViewBoxPoint(page, 650, 340);
    await expect(page.locator('[data-testid^="entity-line_"]')).toHaveCount(lineCountBeforeConstruction + 1);
    const constructionLine = page.locator('[data-testid^="entity-line_"]').last();
    const constructionLineId = await constructionLine.getAttribute("data-entity-id");
    await constructionLine.dispatchEvent("click");
    await clickWorkbenchButton(page, "Show Advanced Constraints");
    const constraintPanel = page.getByTestId("sketchmath-advanced-constraints");
    await constraintPanel.getByRole("button", { name: "Make construction" }).click();
    await expect(page.locator(`[data-entity-id="${constructionLineId}"] line.sketchmath-construction-line`)).toHaveCount(1);

    const points = page.locator('[data-entity-type="point_2d"]');
    const circle = page.locator('[data-entity-type="circle_2d"]').last();
    await expect(points).toHaveCount(8);
    await expect(circle).toBeVisible();
    await expect(page.getByTestId("sketchmath-status")).toContainText("Under-constrained");
    await expect(page.getByTestId("sketchmath-solver-status-detail")).toContainText("can still move");

    await circle.dispatchEvent("click");
    await page.getByLabel("Circle radius").fill("24");
    await clickWorkbenchButton(page, "Apply radius");
    await expect(circle).toHaveAttribute("r", "24");

    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();
    const historyLength = async () => {
      const response = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
      const snapshot = await response.json() as { history_length: number };
      return snapshot.history_length;
    };
    await page.getByRole("button", { name: "Select", exact: true }).click();
    const fixPoint = async (pointIndex: number) => {
      await points.nth(pointIndex).dispatchEvent("click");
      const historyLengthBeforeFix = await historyLength();
      await expect(constraintPanel.getByRole("button", { name: "Fixed", exact: true })).toBeEnabled();
      await constraintPanel.getByRole("button", { name: "Fixed", exact: true }).click();
      await expect.poll(historyLength).toBe(historyLengthBeforeFix + 1);
    };
    await fixPoint(0);

    await fixPoint(1);
    await expect(page.getByTestId("sketchmath-status")).toContainText("Under-constrained");

    const initialCenterX = Number(await points.nth(2).locator("circle").getAttribute("cx"));
    await dispatchPointDragToViewBoxPoint(points.nth(2), 420, 230);
    await expect.poll(async () => Math.abs(Number(await points.nth(2).locator("circle").getAttribute("cx")) - initialCenterX)).toBeGreaterThan(20);
    await expect(page.getByTestId("sketchmath-status")).toContainText("Under-constrained");
    await fixPoint(2);
    await expect(page.getByTestId("sketchmath-status")).toContainText("Under-constrained");
    for (let pointIndex = 3; pointIndex < 8; pointIndex += 1) {
      await fixPoint(pointIndex);
    }
    await expect(page.getByTestId("sketchmath-status")).toContainText("Fully constrained", { timeout: 20000 });
    await expect(page.getByTestId("sketchmath-solver-status-detail")).toContainText("All modeled movement is constrained");

    const beforeConflictResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const beforeConflict = await beforeConflictResponse.json() as { history_length: number };
    const browserErrorCountBeforeConflict = browserErrors.length;
    await dispatchPointDragToViewBoxPoint(points.nth(2), 470, 260);
    await expect(page.getByTestId("sketchmath-user-error")).toContainText("Drag conflicts with fixed point constraint");
    await expect.poll(() => browserErrors.length).toBe(browserErrorCountBeforeConflict + 1);
    expect(browserErrors[browserErrorCountBeforeConflict]).toContain("409 (Conflict)");
    browserErrors.splice(browserErrorCountBeforeConflict, 1);
    const afterConflictResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const afterConflict = await afterConflictResponse.json() as { history_length: number };
    expect(afterConflict.history_length).toBe(beforeConflict.history_length);
    await expect(page.getByTestId("sketchmath-status")).toContainText("Fully constrained");

    await circle.dispatchEvent("click");
    await page.getByLabel("Circle diameter").fill("60");
    await clickWorkbenchButton(page, "Apply diameter");
    await expect(circle).toHaveAttribute("r", "30");
    await expect(page.getByTestId("sketchmath-status")).toContainText("Fully constrained");

    await clickWorkbenchButton(page, "Undo");
    await expect(circle).toHaveAttribute("r", "24");
    await clickWorkbenchButton(page, "Redo");
    await expect(circle).toHaveAttribute("r", "30");

    await constraintPanel.getByRole("button", { name: "Solve constraints" }).click();
    await expect(page.getByTestId("sketchmath-status")).toContainText("Fully constrained");
    const geometryBeforeReload = await page.locator('[data-entity-type="point_2d"] circle, [data-entity-type="circle_2d"]').evaluateAll((entities) =>
      entities.map((entity) => ({
        testId: entity.closest("[data-testid]")?.getAttribute("data-testid"),
        cx: entity.getAttribute("cx"),
        cy: entity.getAttribute("cy"),
        r: entity.getAttribute("r"),
      })),
    );

    await page.reload();
    await expect(page.getByText("SketchMath").first()).toBeVisible();
    await expect(page.getByTestId("sketchmath-status")).toContainText("Fully constrained", { timeout: 20000 });
    await expect(page.locator('[data-entity-type="arc_2d"]')).toHaveCount(1);
    await expect(page.locator(`[data-entity-id="${constructionLineId}"] line.sketchmath-construction-line`)).toHaveCount(1);
    const geometryAfterReload = await page.locator('[data-entity-type="point_2d"] circle, [data-entity-type="circle_2d"]').evaluateAll((entities) =>
      entities.map((entity) => ({
        testId: entity.closest("[data-testid]")?.getAttribute("data-testid"),
        cx: entity.getAttribute("cx"),
        cy: entity.getAttribute("cy"),
        r: entity.getAttribute("r"),
      })),
    );
    expect(geometryAfterReload).toEqual(geometryBeforeReload);
    await page.screenshot({ path: screenshotPath("sketchmath-gate-b-mixed-fully-constrained.png"), fullPage: true });
  });

  test("converts point-backed lines to construction geometry with reload-stable identity", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Line" }).first().click();
    await clickSvgViewBoxPoint(page, 160, 150);
    await clickSvgViewBoxPoint(page, 340, 150);
    const line = page.locator('[data-testid^="entity-line_"]').last();
    const lineId = await line.getAttribute("data-entity-id");
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 1 line");

    await clickWorkbenchButton(page, "Show Advanced Constraints");
    const panel = page.getByTestId("sketchmath-advanced-constraints");
    await panel.getByRole("button", { name: "Make construction" }).click();
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Construction line");
    await expect(line.locator("line.sketchmath-construction-line")).toHaveCount(1);

    await page.reload();
    await expect(page.getByText("SketchMath").first()).toBeVisible();
    const restored = page.locator(`[data-entity-id="${lineId}"]`);
    await expect(restored.locator("line.sketchmath-construction-line")).toHaveCount(1);
    await restored.dispatchEvent("click");
    await clickWorkbenchButton(page, "Show Advanced Constraints");
    await page.getByTestId("sketchmath-advanced-constraints").getByRole("button", { name: "Make regular" }).click();
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 1 line");
  });

  test("creates mixed Gate B geometry, diagnoses an unsafe edit, recovers, and reloads durable history", async ({ page }) => {
    await openSketchMath(page);

    await page.getByRole("button", { name: "Polygon", exact: true }).click();
    await clickSvgViewBoxPoint(page, 250, 220);
    await expect(page.getByTestId("sketchmath-polygon-draft")).toBeAttached();
    await clickSvgViewBoxPoint(page, 310, 220);
    await expect(page.locator('[data-entity-type="profile_2d"]')).toHaveCount(1);
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");

    await page.getByRole("button", { name: "Slot", exact: true }).click();
    await expect(page.getByTestId("sketchmath-canvas-helper")).toContainText("Click the first slot center");
    await dispatchCanvasViewBoxPoint(page, 480, 260);
    await expect(page.getByTestId("sketchmath-canvas-helper")).toContainText("Click the second slot center");
    await dispatchCanvasViewBoxPoint(page, 650, 260);
    await expect(page.locator('[data-entity-type="arc_2d"]')).toHaveCount(2);
    await expect(page.locator('[data-entity-type="profile_2d"]')).toHaveCount(2);
    await expect(page.getByTestId("sketchmath-workflow-extrude")).toContainText("Ready for CAD feature");

    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();
    type GateBSnapshot = {
      history_length: number;
      history: Array<{ command: { command_type: string; parameters: Record<string, unknown> } }>;
      selection_context: { items: Array<{ id: string; type: string; source_curve_ids?: string[] }> };
    };
    const beforeRefusalResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const beforeRefusal = await beforeRefusalResponse.json() as GateBSnapshot;
    const slotProfile = beforeRefusal.selection_context.items.find(
      (entity) => entity.type === "profile_2d" && entity.source_curve_ids?.some((id) => id.includes("slot_")),
    );
    expect(slotProfile?.source_curve_ids).toHaveLength(4);
    const slotSourceLineId = slotProfile?.source_curve_ids?.find((id) =>
      beforeRefusal.selection_context.items.some((entity) => entity.id === id && entity.type === "line_2d"),
    );
    expect(slotSourceLineId).toBeTruthy();
    const idsBeforeRefusal = beforeRefusal.selection_context.items.map((entity) => entity.id).sort();

    const browserErrorCountBeforeRefusal = browserErrors.length;
    await page.locator(`[data-entity-id="${slotSourceLineId}"]`).dispatchEvent("click");
    await page.getByTestId("sketchmath-editing-tools").getByRole("button", { name: "Split midpoint" }).click();
    await expect(page.getByTestId("sketchmath-user-error")).toContainText("Referenced curve cannot be edited without topology repair");
    await expect.poll(() => browserErrors.length).toBe(browserErrorCountBeforeRefusal + 1);
    expect(browserErrors[browserErrorCountBeforeRefusal]).toContain("422 (Unprocessable Entity)");
    browserErrors.splice(browserErrorCountBeforeRefusal, 1);
    const afterRefusalResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const afterRefusal = await afterRefusalResponse.json() as GateBSnapshot;
    expect(afterRefusal.history_length).toBe(beforeRefusal.history_length);
    expect(afterRefusal.selection_context.items.map((entity) => entity.id).sort()).toEqual(idsBeforeRefusal);

    await page.locator(`[data-entity-id="${slotProfile?.id}"]`).dispatchEvent("click");

    await page.getByTestId("sketchmath-editing-tools").getByRole("button", { name: "Duplicate" }).click();
    await expect(page.locator('[data-entity-type="profile_2d"]')).toHaveCount(3);
    await expect(page.locator('[data-entity-type="arc_2d"]')).toHaveCount(4);

    const undo = page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Undo" });
    const redo = page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Redo" });
    await undo.click();
    await expect(page.locator('[data-entity-type="profile_2d"]')).toHaveCount(2);
    await redo.click();
    await expect(page.locator('[data-entity-type="profile_2d"]')).toHaveCount(3);

    await page.getByRole("button", { name: "Circle" }).click();
    await dispatchCanvasViewBoxPoint(page, 760, 160);
    await dispatchCanvasViewBoxPoint(page, 790, 160);
    const circle = page.locator('[data-entity-type="circle_2d"]').last();
    await expect(circle).toBeVisible();
    await page.getByLabel("Offset distance").fill("5");
    await page.getByTestId("sketchmath-editing-tools").getByRole("button", { name: "Offset" }).click();
    await expect(page.locator('[data-entity-type="circle_2d"]')).toHaveCount(2);

    await page.getByRole("button", { name: "Line", exact: true }).click();
    await dispatchCanvasViewBoxPoint(page, 120, 360);
    await expect(page.getByTestId("sketchmath-canvas-helper")).toContainText("Click the line end point");
    await dispatchCanvasViewBoxPoint(page, 300, 360);
    await expect(page.getByTestId("sketchmath-canvas-helper")).toContainText("Click the line start point");
    const constructionLine = page.locator('[data-testid^="entity-line_"]').last();
    const constructionLineId = await constructionLine.getAttribute("data-entity-id");
    await constructionLine.dispatchEvent("click");
    await clickWorkbenchButton(page, "Show Advanced Constraints");
    await page.getByTestId("sketchmath-advanced-constraints").getByRole("button", { name: "Make construction" }).click();
    await expect(page.locator(`[data-entity-id="${constructionLineId}"] line.sketchmath-construction-line`)).toHaveCount(1);

    const beforeSplitLineResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const beforeSplitLine = await beforeSplitLineResponse.json() as GateBSnapshot;
    const entityIdsBeforeSplitLine = new Set(beforeSplitLine.selection_context.items.map((entity) => entity.id));
    await page.getByRole("button", { name: "Line", exact: true }).click();
    await dispatchCanvasViewBoxPoint(page, 150, 430);
    await expect(page.getByTestId("sketchmath-canvas-helper")).toContainText("Click the line end point");
    await dispatchCanvasViewBoxPoint(page, 350, 430);
    await expect(page.getByTestId("sketchmath-canvas-helper")).toContainText("Click the line start point");
    let sourceLineId: string | undefined;
    await expect.poll(async () => {
      const response = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
      const snapshot = await response.json() as GateBSnapshot;
      sourceLineId = snapshot.selection_context.items.find(
        (entity) => entity.type === "line_2d" && !entityIdsBeforeSplitLine.has(entity.id),
      )?.id;
      return Boolean(sourceLineId);
    }).toBe(true);
    const sourceLine = page.locator(`[data-entity-id="${sourceLineId}"]`);
    await expect(sourceLine).toBeAttached();
    await sourceLine.dispatchEvent("click");
    await page.getByTestId("sketchmath-editing-tools").getByRole("button", { name: "Split midpoint" }).click();
    await expect(page.locator('[data-testid^="entity-split_"][data-entity-type="line_2d"]')).toHaveCount(1);
    await expect(page.getByTestId("sketchmath-user-error")).toHaveCount(0);

    await page.locator(`[data-entity-id="${slotProfile?.id}"]`).dispatchEvent("click");
    await page.getByLabel("Pattern count").fill("2");
    await page.getByTestId("sketchmath-editing-tools").getByRole("button", { name: "Linear pattern" }).click();
    await expect(page.locator('[data-entity-type="arc_2d"]')).toHaveCount(8);
    await page.locator(`[data-entity-id="${slotProfile?.id}"]`).dispatchEvent("click");
    await page.getByTestId("sketchmath-editing-tools").getByRole("button", { name: "Mirror about X=0" }).click();
    await expect.poll(async () => {
      const response = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
      const snapshot = await response.json() as GateBSnapshot;
      return snapshot.history.at(-1)?.command.command_type;
    }).toBe("mirror");

    await page.getByRole("button", { name: "Box select", exact: true }).first().click();
    await dragCanvasViewBoxBox(page, { x: 90, y: 330 }, { x: 380, y: 460 });
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText(/Selected: [2-9]/);

    const beforeReloadResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const beforeReload = await beforeReloadResponse.json() as GateBSnapshot;
    const idsBeforeReload = beforeReload.selection_context.items.map((entity) => entity.id).sort();
    const entityTypes = new Set(beforeReload.selection_context.items.map((entity) => entity.type));
    for (const entityType of ["line_2d", "construction_line_2d", "circle_2d", "arc_2d", "profile_2d"]) {
      expect(entityTypes.has(entityType)).toBe(true);
    }
    const commandTypes = beforeReload.history.map((entry) => entry.command.command_type);
    expect(commandTypes).toEqual(expect.arrayContaining([
      "define_regular_polygon",
      "define_slot",
      "copy_linear",
      "mirror",
      "offset_curve",
      "set_construction",
      "split_line",
    ]));

    await page.reload();
    await expect(page.getByText("SketchMath").first()).toBeVisible();
    const afterReloadResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const afterReload = await afterReloadResponse.json() as GateBSnapshot;
    expect(afterReload.selection_context.items.map((entity) => entity.id).sort()).toEqual(idsBeforeReload);
    expect(afterReload.history_length).toBe(beforeReload.history_length);
    await expect(page.locator(`[data-entity-id="${constructionLineId}"] line.sketchmath-construction-line`)).toHaveCount(1);
    await page.screenshot({ path: screenshotPath("sketchmath-gate-b-durable-editing.png"), fullPage: true });
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
    await page.getByRole("button", { name: "Point", exact: true }).click();
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
