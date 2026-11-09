import { expect, test } from "@playwright/test";
import { registerCustomer } from "./helpers";

test("daily spin awards the server result and retains the completed wheel state", async ({ page }) => {
  await registerCustomer(page);
  await page.getByRole("link", { name: /daily spin/i }).click();
  await expect(page).toHaveURL(/\/spin$/);
  await expect(page.getByRole("img", { name: "Daily reward wheel" })).toBeVisible();
  const wheel = page.locator(".reward-wheel");
  const pointer = page.locator(".reward-wheel-pointer");
  await expect(pointer).toBeVisible();
  expect(await pointer.locator("..").getAttribute("class")).toContain("reward-wheel-frame");
  expect(await wheel.locator("..").getAttribute("class")).toContain("reward-wheel-frame");

  const spinResponsePromise = page.waitForResponse(
    (response) => response.url().endsWith("/spin") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: /spin (once today|again)/i }).click();
  const spinResponse = await spinResponsePromise;
  expect(spinResponse.ok()).toBeTruthy();
  const result = await spinResponse.json() as { points_awarded: number; reward_points: number };
  await expect(page.getByRole("status").filter({ hasText: /earned|landed|allowance is used up/i })).toBeVisible();
  await expect(page.getByRole("img", { name: "Daily reward wheel" })).toBeVisible();
  expect(result.points_awarded).toBeGreaterThanOrEqual(0);
  expect(result.points_awarded).toBeLessThanOrEqual(result.reward_points);
  const settledRotation = await wheel.evaluate((element) => getComputedStyle(element).transform);
  await page.waitForTimeout(300);
  await expect(wheel).toHaveCSS("transform", settledRotation);
});
