import { expect, type Page } from "@playwright/test";

export async function registerCustomer(page: Page) {
  const identity = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  const email = `e2e-${identity}@example.com`;
  const password = "e2e-test-password-at-least-12";
  await page.goto("/register");
  await page.getByLabel("Your name").fill("Playwright Customer");
  await page.getByLabel("Email or mobile number").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create my account/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL("/");
  await page.goto("/login");
  await page.getByLabel("Email or mobile number").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /^log in/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  return identity;
}
