import { expect, test } from "@playwright/test";

test.describe("TrustPay PWA smoke", () => {
  test("home renders and links to the check flow", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "TrustPay SEA" })).toBeVisible();
    await page.getByRole("link", { name: /Check an account/ }).click();
    await expect(page).toHaveURL(/\/check/);
    await expect(page.getByRole("heading", { name: "Check before you pay" })).toBeVisible();
  });

  test("scam playbook library renders", async ({ page }) => {
    await page.goto("/playbook");
    await expect(page.getByRole("heading", { name: "Scam Playbooks" })).toBeVisible();
  });

  test("recovery wizard renders", async ({ page }) => {
    await page.goto("/recovery");
    await expect(page.getByRole("heading", { name: "I just got scammed" })).toBeVisible();
  });
});
