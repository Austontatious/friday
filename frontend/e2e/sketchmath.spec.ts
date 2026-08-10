import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { openSketchMath } from "./helpers/sketchmath";

const screenshotPath = (name: string) => `../tmp/sketchmath_sol/${name}`;

const goldenMountingPlateDocument = (): Record<string, unknown> => JSON.parse(execFileSync(
  "python3",
  [
    "-c",
    "from sketchmath.features.golden_mounting_plate import build_golden_mounting_plate; print(build_golden_mounting_plate().model_dump_json())",
  ],
  { cwd: path.resolve(__dirname, "../.."), encoding: "utf8" },
));

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
    await expect(page.getByLabel("Extrusion depth", { exact: true })).toHaveValue("10");
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
        features: Array<{
          feature_id: string;
          feature_type: "extrude" | "hole";
          parameters: { depth_mm?: number | null; diameter_mm?: number; termination?: "through" | "blind" };
        }>;
        artifacts: Array<{ feature_id: string; revision: number; format: string; path: string }>;
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
    await panel.getByRole("button", { name: "Apply extrusion" }).click();
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

    await page.getByTestId(`sketchmath-feature-${featureId}`).getByRole("button", { name: "Build STL" }).click();
    await expect(page.getByTestId(`sketchmath-artifact-status-${featureId}`)).toContainText("DONE · complete · revision 5", { timeout: 15000 });
    const artifactResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const artifactSnapshot = await artifactResponse.json() as FeatureSnapshot;
    expect(artifactSnapshot.document.artifacts).toHaveLength(1);
    expect(artifactSnapshot.document.artifacts[0]).toMatchObject({ feature_id: featureId, revision: 5, format: "stl" });

    await page.reload();
    const stlDownload = page.getByTestId(`sketchmath-artifact-download-${featureId}`);
    await expect(stlDownload).toBeVisible();
    const downloadPromise = page.waitForEvent("download");
    await stlDownload.click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.stl$/);

    await page.getByLabel(`Hole diameter ${featureId}`).fill("20");
    await page.getByTestId(`sketchmath-hole-editor-${featureId}`).getByRole("button", { name: "Add simple hole" }).click();
    await expect(page.getByTestId("sketchmath-feature-history-panel")).toContainText("Revision 6");
    const holeResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const withHole = await holeResponse.json() as FeatureSnapshot;
    const holeFeature = withHole.document.features.find((feature) => feature.feature_type === "hole");
    expect(holeFeature).toBeTruthy();
    const holeFeatureId = holeFeature!.feature_id;
    expect(holeFeature?.parameters.diameter_mm).toBe(20);
    expect(withHole.document.last_rebuild.records[1]).toMatchObject({ feature_id: holeFeatureId });

    const existingHoleEditor = page.getByTestId(`sketchmath-existing-hole-editor-${holeFeatureId}`);
    await existingHoleEditor.getByLabel("Existing hole diameter Hole 1").fill("18");
    await existingHoleEditor.getByRole("button", { name: "Through" }).click();
    await existingHoleEditor.getByLabel("Existing hole depth Hole 1").fill("10");
    await existingHoleEditor.getByRole("button", { name: "Apply hole" }).click();
    await expect(panel).toContainText("Revision 7");
    await panel.getByRole("button", { name: "Undo feature" }).click();
    await expect(existingHoleEditor.getByLabel("Existing hole diameter Hole 1")).toHaveValue("20");
    await panel.getByRole("button", { name: "Redo feature" }).click();
    await expect(existingHoleEditor.getByLabel("Existing hole diameter Hole 1")).toHaveValue("18");
    await expect(existingHoleEditor.getByLabel("Existing hole depth Hole 1")).toHaveValue("10");

    await page.getByLabel(`Feature depth ${featureId}`).fill("30");
    await page.getByTestId(`sketchmath-feature-${featureId}`).getByRole("button", { name: "Apply extrusion" }).click();
    await expect(page.getByTestId("sketchmath-feature-history-panel")).toContainText("Revision 10");
    const recoveredResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const recovered = await recoveredResponse.json() as FeatureSnapshot & {
      document: FeatureSnapshot["document"] & {
        last_rebuild: { records: Array<{ feature_id: string; output_signature: string; resolved_references?: Array<{ recovery_state: string }> }> };
      };
    };
    expect(recovered.document.last_rebuild.records[1].resolved_references?.[0].recovery_state).toBe("recovered");

    await page.reload();
    const holeRow = page.getByTestId(`sketchmath-feature-${holeFeatureId}`);
    await expect(holeRow).toContainText("hole · cut · succeeded");
    await expect(holeRow.getByLabel("Existing hole diameter Hole 1")).toHaveValue("18");
    await expect(holeRow.getByLabel("Existing hole depth Hole 1")).toHaveValue("10");
    await holeRow.getByRole("button", { name: "Build STL" }).click();
    await expect(page.getByTestId(`sketchmath-artifact-status-${holeFeatureId}`)).toContainText("DONE · complete · revision 10", { timeout: 15000 });
    const graphDownload = page.getByTestId(`sketchmath-artifact-download-${holeFeatureId}`);
    const graphDownloadPromise = page.waitForEvent("download");
    await graphDownload.click();
    expect((await graphDownloadPromise).suggestedFilename()).toMatch(/\.stl$/);
  });

  test("edits extrusion direction and extent with deterministic rebuild history", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 160, 120);
    await clickSvgViewBoxPoint(page, 360, 220);
    const panel = page.getByTestId("sketchmath-feature-history-panel");
    await page.getByLabel("Feature extrusion depth").fill("10");
    await panel.getByRole("button", { name: "Add extrusion feature" }).click();
    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();
    type ExtrusionSnapshot = {
      document: {
        features: Array<{ feature_id: string; parameters: Record<string, any> }>;
        last_rebuild: { records: Array<{ output_signature: string; measurements: { bounds_mm: number[] } }> };
      };
      feature_history_length: number;
    };
    const created = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as ExtrusionSnapshot;
    const featureId = created.document.features[0].feature_id;
    const editor = page.getByTestId(`sketchmath-feature-${featureId}`);

    await editor.getByLabel(`Feature extent ${featureId}`).selectOption("symmetric");
    await editor.getByLabel(`Feature direction ${featureId}`).selectOption("negative");
    await editor.getByRole("button", { name: "Apply extrusion" }).click();
    const symmetric = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as ExtrusionSnapshot;
    expect(symmetric.document.features[0]).toMatchObject({
      feature_id: featureId,
      parameters: { depth_mm: 10, extent: "symmetric", direction: "negative", second_depth_mm: null },
    });
    expect(symmetric.document.last_rebuild.records[0].measurements.bounds_mm.slice(-2)).toEqual([-5, 5]);

    await editor.getByLabel(`Feature extent ${featureId}`).selectOption("two_sided");
    await editor.getByLabel(`Feature direction ${featureId}`).selectOption("positive");
    await editor.getByLabel(`Feature second depth ${featureId}`).fill("4");
    await editor.getByRole("button", { name: "Apply extrusion" }).click();
    const twoSided = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as ExtrusionSnapshot;
    expect(twoSided.document.features[0]).toMatchObject({
      feature_id: featureId,
      parameters: { depth_mm: 10, extent: "two_sided", direction: "positive", second_depth_mm: 4 },
    });
    expect(twoSided.document.last_rebuild.records[0].measurements.bounds_mm.slice(-2)).toEqual([-4, 10]);
    expect(twoSided.document.last_rebuild.records[0].output_signature).not.toBe(symmetric.document.last_rebuild.records[0].output_signature);

    await panel.getByRole("button", { name: "Undo feature" }).click();
    await expect(editor.getByLabel(`Feature extent ${featureId}`)).toHaveValue("symmetric");
    await panel.getByRole("button", { name: "Redo feature" }).click();
    await expect(editor.getByLabel(`Feature extent ${featureId}`)).toHaveValue("two_sided");
    await expect(editor.getByLabel(`Feature second depth ${featureId}`)).toHaveValue("4");

    await page.reload();
    await expect(page.getByLabel(`Feature extent ${featureId}`)).toHaveValue("two_sided");
    await expect(page.getByLabel(`Feature direction ${featureId}`)).toHaveValue("positive");
    await expect(page.getByLabel(`Feature second depth ${featureId}`)).toHaveValue("4");
    const reloaded = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as ExtrusionSnapshot;
    expect(reloaded.feature_history_length).toBe(3);
    expect(reloaded.document.features[0].feature_id).toBe(featureId);
  });

  test("creates an explicit semantic cut extrusion into the target body", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 160, 120);
    await clickSvgViewBoxPoint(page, 360, 220);
    const panel = page.getByTestId("sketchmath-feature-history-panel");
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");
    await page.getByLabel("Feature extrusion depth").fill("10");
    await expect(panel.getByRole("button", { name: "Add extrusion feature" })).toBeEnabled();
    await panel.getByRole("button", { name: "Add extrusion feature" }).click();

    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await dispatchCanvasViewBoxPoint(page, 220, 150);
    await dispatchCanvasViewBoxPoint(page, 300, 210);
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");
    await page.getByLabel("Feature extrusion depth").fill("4");
    await page.getByLabel("New extrusion operation").selectOption("cut");
    await panel.getByRole("button", { name: "Add extrusion feature" }).click();

    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();
    type CutSnapshot = {
      document: {
        revision: number;
        features: Array<{ feature_id: string; dependencies: string[]; parameters: Record<string, any> }>;
        artifacts: Array<{ feature_id: string; format: string; revision: number }>;
        last_rebuild: { records: Array<{ status: string; measurements: { volume_delta_mm3: number; bounds_mm: number[] }; resolved_references: Array<{ recovery_state: string }> }> };
      };
    };
    const cut = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as CutSnapshot;
    expect(cut.document.features).toHaveLength(2);
    expect(cut.document.features[1]).toMatchObject({
      dependencies: [cut.document.features[0].feature_id],
      parameters: { operation: "cut", direction: "negative", extent: "one_sided", depth_mm: 4 },
    });
    expect(cut.document.last_rebuild.records[1].status).toBe("succeeded");
    expect(cut.document.last_rebuild.records[1].measurements.volume_delta_mm3).toBeLessThan(0);
    expect(cut.document.last_rebuild.records[1].measurements.bounds_mm.slice(-2)).toEqual([6, 10]);
    expect(cut.document.last_rebuild.records[1].resolved_references[0].recovery_state).toBe("exact");

    await panel.getByRole("button", { name: "Undo feature" }).click();
    await expect(page.getByTestId("sketchmath-model-tree")).not.toContainText("Extrude 2");
    await panel.getByRole("button", { name: "Redo feature" }).click();
    await expect(page.getByTestId("sketchmath-model-tree")).toContainText("Extrude 2");
    await page.reload();
    const reloaded = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as CutSnapshot;
    expect(reloaded.document.features[1].parameters.operation).toBe("cut");
    expect(reloaded.document.features[1].feature_id).toBe(cut.document.features[1].feature_id);
    const cutFeatureId = reloaded.document.features[1].feature_id;
    const cutRow = page.getByTestId(`sketchmath-feature-${cutFeatureId}`);
    await cutRow.getByRole("button", { name: "Build STL" }).click();
    await expect(page.getByTestId(`sketchmath-artifact-status-${cutFeatureId}`)).toContainText(
      `DONE · complete · revision ${reloaded.document.revision}`,
      { timeout: 15000 },
    );
    const download = page.getByTestId(`sketchmath-artifact-download-${cutFeatureId}`);
    const downloadPromise = page.waitForEvent("download");
    await download.click();
    expect((await downloadPromise).suggestedFilename()).toMatch(/\.stl$/);
    const withArtifact = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as CutSnapshot;
    expect(withArtifact.document.artifacts).toContainEqual(expect.objectContaining({
      feature_id: cutFeatureId,
      format: "stl",
      revision: reloaded.document.revision,
    }));
    await cutRow.getByRole("button", { name: "Build STEP" }).click();
    await expect(page.getByTestId(`sketchmath-artifact-status-${cutFeatureId}`)).toContainText(
      `DONE · complete · revision ${reloaded.document.revision}`,
      { timeout: 15000 },
    );
    const stepDownload = page.getByTestId(`sketchmath-artifact-download-${cutFeatureId}`);
    const stepDownloadPromise = page.waitForEvent("download");
    await stepDownload.click();
    expect((await stepDownloadPromise).suggestedFilename()).toMatch(/\.step$/);
    const withStep = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as CutSnapshot;
    expect(withStep.document.artifacts).toContainEqual(expect.objectContaining({
      feature_id: cutFeatureId,
      format: "step",
      revision: reloaded.document.revision,
    }));
  });

  test("edits a full revolve axis with stable history and reload identity", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 300, 140);
    await clickSvgViewBoxPoint(page, 420, 240);
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");

    await clickWorkbenchButton(page, "Show Advanced Constraints");
    for (const [index, x] of [280, 290].entries()) {
      await page.getByRole("button", { name: "Select", exact: true }).click();
      await dispatchCanvasViewBoxPoint(page, 500, 300);
      await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Nothing");
      await page.getByRole("button", { name: "Line" }).first().click();
      await dispatchCanvasViewBoxPoint(page, x, 150);
      await expect(page.getByTestId("sketchmath-canvas-helper")).toContainText("Click the line end point");
      await dispatchCanvasViewBoxPoint(page, x, 230);
      await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: 1 line");
      await page.getByTestId("sketchmath-advanced-constraints").getByRole("button", { name: "Make construction" }).click();
      await expect(page.locator('[data-entity-type="construction_line_2d"]')).toHaveCount(index + 1);
    }

    await page.locator('[data-entity-type="profile_2d"]').last().dispatchEvent("click");
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");
    const panel = page.getByTestId("sketchmath-feature-history-panel");
    const constructionAxisIds = await panel.getByLabel("Revolve axis").locator("option").evaluateAll((options) => (
      options.map((option) => (option as HTMLOptionElement).value).filter(Boolean)
    ));
    expect(constructionAxisIds).toHaveLength(2);
    expect(constructionAxisIds[0]).not.toBe(constructionAxisIds[1]);
    await panel.getByLabel("Revolve axis").selectOption(constructionAxisIds[0]);
    await panel.getByRole("button", { name: "Add full revolve" }).click();
    await expect(panel).toContainText("Rebuild passed · 1 feature");
    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();

    type RevolveSnapshot = {
      document: {
        revision: number;
        features: Array<{
          feature_id: string;
          feature_type: string;
          parameters: { axis_entity_id: string; angle_deg: number };
        }>;
        last_rebuild: { records: Array<{ feature_id: string; output_signature: string }> };
      };
      feature_history_length: number;
    };
    const created = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as RevolveSnapshot;
    const feature = created.document.features[0];
    const featureId = feature.feature_id;
    const initialSignature = created.document.last_rebuild.records[0].output_signature;
    expect(feature).toMatchObject({
      feature_type: "revolve",
      parameters: { axis_entity_id: constructionAxisIds[0], angle_deg: 360 },
    });

    const editor = page.getByTestId(`sketchmath-existing-revolve-editor-${featureId}`);
    await editor.getByLabel("Revolve axis Revolve 1").selectOption(constructionAxisIds[1]);
    await expect(editor.getByLabel("Revolve axis Revolve 1")).toHaveValue(constructionAxisIds[1]);
    await expect(editor.getByRole("button", { name: "Apply revolve" })).toBeEnabled();
    await editor.getByRole("button", { name: "Apply revolve" }).click();
    const replaced = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as RevolveSnapshot;
    expect(replaced.document.features[0].feature_id).toBe(featureId);
    expect(replaced.document.features[0].parameters.axis_entity_id).toBe(constructionAxisIds[1]);
    expect(replaced.document.last_rebuild.records[0].output_signature).not.toBe(initialSignature);

    await panel.getByRole("button", { name: "Undo feature" }).click();
    await expect(editor.getByLabel("Revolve axis Revolve 1")).toHaveValue(constructionAxisIds[0]);
    await panel.getByRole("button", { name: "Redo feature" }).click();
    await expect(editor.getByLabel("Revolve axis Revolve 1")).toHaveValue(constructionAxisIds[1]);

    await page.reload();
    await expect(page.getByText("SketchMath").first()).toBeVisible();
    const reloaded = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as RevolveSnapshot;
    expect(reloaded.document.features[0].feature_id).toBe(featureId);
    expect(reloaded.document.features[0].parameters.axis_entity_id).toBe(constructionAxisIds[1]);
    expect(reloaded.document.last_rebuild.records[0].output_signature).toBe(replaced.document.last_rebuild.records[0].output_signature);
    expect(reloaded.feature_history_length).toBe(2);
    await expect(page.getByLabel("Revolve axis Revolve 1")).toHaveValue(constructionAxisIds[1]);
  });

  test("edits counterbore and countersink hole properties through durable history", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 140, 120);
    await clickSvgViewBoxPoint(page, 360, 240);
    const panel = page.getByTestId("sketchmath-feature-history-panel");
    await page.getByLabel("Feature extrusion depth").fill("12");
    await panel.getByRole("button", { name: "Add extrusion feature" }).click();

    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();
    type AdvancedHoleSnapshot = {
      document: {
        features: Array<{
          feature_id: string;
          feature_type: string;
          parameters: Record<string, any>;
        }>;
      };
      feature_history_length: number;
    };
    const base = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as AdvancedHoleSnapshot;
    const baseFeatureId = base.document.features[0].feature_id;
    const baseRow = page.getByTestId(`sketchmath-feature-${baseFeatureId}`);
    await baseRow.getByLabel(`Hole diameter ${baseFeatureId}`).fill("4");
    await baseRow.getByRole("button", { name: "Add simple hole" }).click();

    const withSimple = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as AdvancedHoleSnapshot;
    const holeFeature = withSimple.document.features.find((feature) => feature.feature_type === "hole");
    expect(holeFeature).toBeTruthy();
    const holeFeatureId = holeFeature!.feature_id;
    const editor = page.getByTestId(`sketchmath-existing-hole-editor-${holeFeatureId}`);

    await editor.getByLabel("Existing hole style Hole 1").selectOption("counterbore");
    await editor.getByLabel("Counterbore diameter Hole 1").fill("8");
    await editor.getByLabel("Counterbore depth Hole 1").fill("2");
    await editor.getByRole("button", { name: "Apply hole" }).click();
    const counterbored = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as AdvancedHoleSnapshot;
    expect(counterbored.document.features.find((feature) => feature.feature_id === holeFeatureId)?.parameters).toMatchObject({
      style: "counterbore",
      diameter_mm: 4,
      counterbore_diameter_mm: 8,
      counterbore_depth_mm: 2,
    });

    await editor.getByLabel("Existing hole style Hole 1").selectOption("countersink");
    await editor.getByLabel("Countersink diameter Hole 1").fill("10");
    await editor.getByLabel("Countersink angle Hole 1").fill("82");
    await editor.getByRole("button", { name: "Apply hole" }).click();
    const countersunk = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as AdvancedHoleSnapshot;
    expect(countersunk.document.features.find((feature) => feature.feature_id === holeFeatureId)?.parameters).toMatchObject({
      style: "countersink",
      diameter_mm: 4,
      countersink_diameter_mm: 10,
      countersink_angle_deg: 82,
      counterbore_diameter_mm: null,
      counterbore_depth_mm: null,
    });

    await panel.getByRole("button", { name: "Undo feature" }).click();
    await expect(editor.getByLabel("Existing hole style Hole 1")).toHaveValue("counterbore");
    await expect(editor.getByLabel("Counterbore diameter Hole 1")).toHaveValue("8");
    await panel.getByRole("button", { name: "Redo feature" }).click();
    await expect(editor.getByLabel("Existing hole style Hole 1")).toHaveValue("countersink");

    await page.reload();
    await expect(page.getByText("SketchMath").first()).toBeVisible();
    await expect(page.getByLabel("Existing hole style Hole 1")).toHaveValue("countersink");
    await expect(page.getByLabel("Countersink diameter Hole 1")).toHaveValue("10");
    await expect(page.getByLabel("Countersink angle Hole 1")).toHaveValue("82");
    const reloaded = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as AdvancedHoleSnapshot;
    expect(reloaded.feature_history_length).toBe(4);
    expect(reloaded.document.features.find((feature) => feature.feature_id === holeFeatureId)?.feature_id).toBe(holeFeatureId);
  });

  test("selects semantic model-tree nodes and persists a feature rename", async ({ page }) => {
    await openSketchMath(page);
    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();

    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 140, 120);
    await clickSvgViewBoxPoint(page, 360, 200);
    const panel = page.getByTestId("sketchmath-feature-history-panel");
    await page.getByLabel("Feature extrusion depth").fill("12");
    await panel.getByRole("button", { name: "Add extrusion feature" }).click();
    await expect(panel).toContainText("Revision 2");

    const snapshot = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as {
      document: { features: Array<{ feature_id: string; name: string }> };
    };
    const featureId = snapshot.document.features[0].feature_id;
    const tree = page.getByTestId("sketchmath-model-tree");
    await expect(tree).toContainText("Body · Main body");
    await expect(tree).toContainText("Sketch · Main sketch");
    await expect(tree).toContainText("Extrude · Extrude 1");
    await expect(tree).not.toContainText(featureId);

    await tree.getByRole("button", { name: "Extrude · Extrude 1" }).click();
    await expect(page.getByTestId("sketchmath-model-properties")).toContainText("Depth 12 mm");
    await page.getByLabel("Selected feature name").fill("Primary pad");
    await page.getByRole("button", { name: "Rename feature" }).click();
    await expect(panel).toContainText("Revision 3");
    await expect(tree).toContainText("Extrude · Primary pad");

    const renamed = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as {
      document: { features: Array<{ feature_id: string; name: string; parameters: { depth_mm: number } }> };
    };
    expect(renamed.document.features[0]).toMatchObject({
      feature_id: featureId,
      name: "Primary pad",
      parameters: { depth_mm: 12 },
    });

    await page.reload();
    await expect(page.getByTestId("sketchmath-model-tree")).toContainText("Extrude · Primary pad");
    await expect(page.getByLabel("Selected feature name")).toHaveValue("Primary pad");
  });

  test("edits the golden mounting plate parametrically and exports the rebuilt STEP", async ({ page }) => {
    const createdResponse = await page.request.post("/api/sketchmath/sessions", {
      data: { document: goldenMountingPlateDocument() },
    });
    expect(createdResponse.ok()).toBeTruthy();
    const created = await createdResponse.json() as { session_id: string };
    await page.addInitScript((sessionId) => {
      window.localStorage.setItem("friday_sketchmath_session_id", sessionId);
    }, created.session_id);
    await openSketchMath(page);

    const panel = page.getByTestId("sketchmath-feature-history-panel");
    await expect(panel).toContainText("Revision 8");
    await expect(page.getByTestId("sketchmath-model-tree")).toContainText("Fillet · Outer edge fillets");
    await expect(page.getByTestId("sketchmath-model-tree")).not.toContainText("feature_outer_fillet");

    const widthEditor = page.getByTestId("sketchmath-design-parameter-plate_width_mm");
    await widthEditor.getByLabel("Plate width").fill("100");
    await widthEditor.getByRole("button", { name: "Apply" }).click();
    await expect(panel).toContainText("Revision 9");

    const diameterEditor = page.getByTestId("sketchmath-design-parameter-corner_hole_diameter_mm");
    await diameterEditor.getByLabel("Corner-hole diameter").fill("6");
    await diameterEditor.getByRole("button", { name: "Apply" }).click();
    await expect(panel).toContainText("Revision 10");

    type GoldenSnapshot = {
      selection_context: {
        items: Array<{ id: string; area?: number; center?: [number, number] }>;
      };
      document: {
        revision: number;
        design_parameters: Array<{ parameter_id: string; value: number }>;
        features: Array<{
          feature_id: string;
          feature_type: string;
          parameters: { position_mm?: [number, number]; diameter_mm?: number };
        }>;
        artifacts: Array<{ revision: number; format: string; metadata: Record<string, any> }>;
      };
    };
    const edited = await (await page.request.get(`/api/sketchmath/sessions/${created.session_id}`)).json() as GoldenSnapshot;
    const features = Object.fromEntries(edited.document.features.map((feature) => [feature.feature_id, feature]));
    const sketchEntities = Object.fromEntries(edited.selection_context.items.map((entity) => [entity.id, entity]));
    expect(edited.document.design_parameters.map((parameter) => parameter.value)).toEqual([100, 6]);
    expect(sketchEntities.profile_plate.area).toBe(5000);
    expect(sketchEntities.circle_boss.center).toEqual([50, 25]);
    expect(features.feature_mount_hole_2.parameters.position_mm).toEqual([93, 7]);
    expect(features.feature_mount_hole_3.parameters.position_mm).toEqual([93, 43]);
    expect(features.feature_boss_hole.parameters.position_mm).toEqual([50, 25]);
    const cornerHoles = edited.document.features.filter((feature) => feature.feature_id.startsWith("feature_mount_hole_"));
    expect(cornerHoles).toHaveLength(4);
    expect(cornerHoles.every((feature) => feature.parameters.diameter_mm === 6)).toBe(true);

    await panel.getByRole("button", { name: "Undo feature" }).click();
    await expect(diameterEditor.getByLabel("Corner-hole diameter")).toHaveValue("5");
    await panel.getByRole("button", { name: "Redo feature" }).click();
    await expect(diameterEditor.getByLabel("Corner-hole diameter")).toHaveValue("6");

    await page.reload();
    await expect(page.getByLabel("Plate width")).toHaveValue("100");
    await expect(page.getByLabel("Corner-hole diameter")).toHaveValue("6");
    const filletRow = page.getByTestId("sketchmath-feature-feature_outer_fillet");
    await filletRow.getByRole("button", { name: "Build STEP" }).click();
    await expect(page.getByTestId("sketchmath-artifact-status-feature_outer_fillet")).toContainText(
      "STEP artifact · DONE · complete · revision 12",
      { timeout: 30000 },
    );

    const artifactSnapshot = await (await page.request.get(`/api/sketchmath/sessions/${created.session_id}`)).json() as GoldenSnapshot;
    const artifact = artifactSnapshot.document.artifacts[0];
    expect(artifact).toMatchObject({ revision: 12, format: "step" });
    const bbox = artifact.metadata.measurements.bbox;
    expect(bbox.xmin).toBeCloseTo(0, 8);
    expect(bbox.xmax).toBeCloseTo(100, 8);
    expect(bbox.ymin).toBeCloseTo(0, 8);
    expect(bbox.ymax).toBeCloseTo(50, 8);
    expect(bbox.zmin).toBeCloseTo(0, 8);
    expect(bbox.zmax).toBeCloseTo(13, 8);
    expect(artifact.metadata.measurements.canonical_hole_count).toBe(5);
    expect(artifact.metadata.measurements.volume_mm3).toBeCloseTo(24_920 + 1_315 * Math.PI, 4);

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("sketchmath-artifact-download-feature_outer_fillet").click();
    expect((await downloadPromise).suggestedFilename()).toMatch(/\.step$/);
  });

  test("creates an outer-edge fillet and downloads its revisioned kernel STEP", async ({ page }) => {
    await openSketchMath(page);
    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();

    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 140, 120);
    await clickSvgViewBoxPoint(page, 360, 200);
    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");
    const panel = page.getByTestId("sketchmath-feature-history-panel");
    await page.getByLabel("Feature extrusion depth").fill("10");
    await panel.getByRole("button", { name: "Add extrusion feature" }).click();
    await expect(panel).toContainText("Revision 2");

    const baseResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const baseSnapshot = await baseResponse.json() as {
      document: { features: Array<{ feature_id: string; feature_type: string }> };
    };
    const baseFeatureId = baseSnapshot.document.features[0].feature_id;
    const baseRow = page.getByTestId(`sketchmath-feature-${baseFeatureId}`);
    await baseRow.getByLabel(`Fillet radius ${baseFeatureId}`).fill("3");
    await baseRow.getByRole("button", { name: "Fillet outer edges" }).click();
    await expect(panel).toContainText("Revision 3");

    const filletResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const filletSnapshot = await filletResponse.json() as {
      document: {
        features: Array<{ feature_id: string; feature_type: string; parameters: { radius_mm?: number } }>;
        last_rebuild: { records: Array<{ feature_id: string; measurement_coverage?: string; resolved_references: unknown[] }> };
      };
    };
    const filletFeature = filletSnapshot.document.features.find((feature) => feature.feature_type === "fillet");
    expect(filletFeature?.parameters.radius_mm).toBe(3);
    const filletFeatureId = filletFeature!.feature_id;
    const filletRecord = filletSnapshot.document.last_rebuild.records.find((record) => record.feature_id === filletFeatureId);
    expect(filletRecord?.measurement_coverage).toBe("kernel_required");
    expect(filletRecord?.resolved_references).toHaveLength(4);

    const filletRow = page.getByTestId(`sketchmath-feature-${filletFeatureId}`);
    await expect(filletRow).toContainText("Measurements require a validated kernel artifact.");
    await filletRow.getByRole("button", { name: "Build STEP" }).click();
    await expect(page.getByTestId(`sketchmath-artifact-status-${filletFeatureId}`)).toContainText(
      "STEP artifact · DONE · complete · revision 3",
      { timeout: 20000 },
    );
    const artifactResponse = await page.request.get(`/api/sketchmath/sessions/${sessionId}`);
    const artifactSnapshot = await artifactResponse.json() as {
      document: { artifacts: Array<{ feature_id: string; revision: number; format: string; metadata: Record<string, any> }> };
    };
    expect(artifactSnapshot.document.artifacts).toHaveLength(1);
    expect(artifactSnapshot.document.artifacts[0]).toMatchObject({ feature_id: filletFeatureId, revision: 3, format: "step" });
    expect(artifactSnapshot.document.artifacts[0].metadata.measurements.reference_policy).toBe("semantic_endpoints_unique_match");

    const stepDownload = page.getByTestId(`sketchmath-artifact-download-${filletFeatureId}`);
    const downloadPromise = page.waitForEvent("download");
    await stepDownload.click();
    expect((await downloadPromise).suggestedFilename()).toMatch(/\.step$/);

    await page.reload();
    await expect(page.getByLabel(`Fillet radius ${filletFeatureId}`)).toHaveValue("3");
    await expect(page.getByTestId(`sketchmath-artifact-download-${filletFeatureId}`)).toBeVisible();
  });

  test("creates an outer-edge chamfer and downloads its revisioned kernel STEP", async ({ page }) => {
    await openSketchMath(page);
    const sessionId = await page.evaluate(() => window.localStorage.getItem("friday_sketchmath_session_id"));
    expect(sessionId).toBeTruthy();

    await page.getByRole("button", { name: "Rectangle" }).first().click();
    await clickSvgViewBoxPoint(page, 140, 120);
    await clickSvgViewBoxPoint(page, 360, 200);
    const panel = page.getByTestId("sketchmath-feature-history-panel");
    await page.getByLabel("Feature extrusion depth").fill("10");
    await panel.getByRole("button", { name: "Add extrusion feature" }).click();
    await expect(panel).toContainText("Revision 2");

    const baseSnapshot = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as {
      document: { features: Array<{ feature_id: string }> };
    };
    const baseFeatureId = baseSnapshot.document.features[0].feature_id;
    const baseRow = page.getByTestId(`sketchmath-feature-${baseFeatureId}`);
    await baseRow.getByLabel(`Chamfer distance ${baseFeatureId}`).fill("3");
    await baseRow.getByRole("button", { name: "Chamfer outer edges" }).click();
    await expect(panel).toContainText("Revision 3");

    const chamferSnapshot = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as {
      document: {
        features: Array<{ feature_id: string; feature_type: string; parameters: { distance_mm?: number } }>;
        last_rebuild: { records: Array<{ feature_id: string; measurement_coverage?: string; resolved_references: unknown[] }> };
      };
    };
    const chamferFeature = chamferSnapshot.document.features.find((feature) => feature.feature_type === "chamfer");
    expect(chamferFeature?.parameters.distance_mm).toBe(3);
    const chamferFeatureId = chamferFeature!.feature_id;
    const chamferRecord = chamferSnapshot.document.last_rebuild.records.find((record) => record.feature_id === chamferFeatureId);
    expect(chamferRecord?.measurement_coverage).toBe("kernel_required");
    expect(chamferRecord?.resolved_references).toHaveLength(4);

    const chamferRow = page.getByTestId(`sketchmath-feature-${chamferFeatureId}`);
    await chamferRow.getByRole("button", { name: "Build STEP" }).click();
    await expect(page.getByTestId(`sketchmath-artifact-status-${chamferFeatureId}`)).toContainText(
      "STEP artifact · DONE · complete · revision 3",
      { timeout: 20000 },
    );
    const artifactSnapshot = await (await page.request.get(`/api/sketchmath/sessions/${sessionId}`)).json() as {
      document: { artifacts: Array<{ feature_id: string; revision: number; format: string; metadata: Record<string, any> }> };
    };
    expect(artifactSnapshot.document.artifacts[0]).toMatchObject({ feature_id: chamferFeatureId, revision: 3, format: "step" });
    expect(artifactSnapshot.document.artifacts[0].metadata.measurements.distance_mm).toBe(3);
    expect(artifactSnapshot.document.artifacts[0].metadata.measurements.reference_policy).toBe("semantic_endpoints_unique_match");

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId(`sketchmath-artifact-download-${chamferFeatureId}`).click();
    expect((await downloadPromise).suggestedFilename()).toMatch(/\.step$/);
    await page.reload();
    await expect(page.getByLabel(`Chamfer distance ${chamferFeatureId}`)).toHaveValue("3");
  });

  test("creates a center-defined rectangle through the canonical rectangle bundle", async ({ page }) => {
    await openSketchMath(page);
    await page.getByRole("button", { name: "Center rectangle", exact: true }).click();
    await clickSvgViewBoxPoint(page, 260, 180);
    await clickSvgViewBoxPoint(page, 340, 230);

    await expect(page.getByTestId("sketchmath-selection-summary")).toContainText("Selected: Profile");
    const dimensionPanel = page.getByTestId("sketchmath-workflow-dimensions");
    const rectangleWidth = dimensionPanel.getByLabel("Rectangle width");
    const rectangleHeight = dimensionPanel.getByLabel("Rectangle height");
    await expect.poll(async () => Math.abs(Number(await rectangleWidth.inputValue()) - 160)).toBeLessThan(3);
    await expect.poll(async () => Math.abs(Number(await rectangleHeight.inputValue()) - 100)).toBeLessThan(3);
    const widthBeforeReload = Number(await rectangleWidth.inputValue());
    const heightBeforeReload = Number(await rectangleHeight.inputValue());
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

    const undo = page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Undo", exact: true });
    const redo = page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Redo", exact: true });
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

    const undo = page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Undo", exact: true });
    const redo = page.getByTestId("sketchmath-workbench-panel").getByRole("button", { name: "Redo", exact: true });
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
