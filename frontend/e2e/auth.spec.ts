import { expect, test } from "@playwright/test";
import { registerCustomer } from "./helpers";

test("customer registration creates an authenticated wallet and rejects invalid login", async ({ page }) => {
  await registerCustomer(page);
  await expect(page.getByText("YOUR POINTS BALANCE")).toBeVisible();
  await expect(page.getByText("1 pts", { exact: true })).toBeVisible();
  await expect(page.getByText(/1 grams of raw chicken/)).toBeVisible();

  await page.getByRole("button", { name: "Log out" }).click();
  await page.goto("/login");
  await page.getByLabel("Email or mobile number").fill("unknown-customer@example.com");
  await page.getByLabel("Password").fill("invalid-password");
  await page.getByRole("button", { name: /^log in/i }).click();
  await expect(page.locator(".form-error")).toContainText(/invalid|credentials/i);
});
