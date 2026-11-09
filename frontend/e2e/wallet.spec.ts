import { expect, test } from "@playwright/test";
import { registerCustomer } from "./helpers";

test("daily login reward persists in wallet transaction history", async ({ page }) => {
  await registerCustomer(page);
  await expect(page.getByText("Daily login reward")).toBeVisible();
  await page.getByRole("link", { name: /full history/i }).click();

  await expect(page).toHaveURL(/\/transactions$/);
  await expect(page.getByRole("heading", { name: "Transaction history" })).toBeVisible();
  const history = page.locator(".transaction-history-list");
  await expect(history.getByText("Daily login reward", { exact: true })).toBeVisible();
  await expect(history.getByText("+1 pts", { exact: true })).toBeVisible();

  await page.reload();
  await expect(page.locator(".transaction-history-list").getByText("Daily login reward", { exact: true })).toBeVisible();
});
