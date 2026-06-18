import { expect } from "@playwright/test";
import type { Page } from "@playwright/test";

export const openSketchMath = async (page: Page) => {
  await page.goto(`/tools/sketchmath?v=${Date.now()}`);
  await expect(page.getByText("Session: loading")).toHaveCount(0);
};

export const clickCanvas = async (page: Page, x: number, y: number) => {
  await page.getByTestId("sketchmath-canvas").click({ position: { x, y } });
};
