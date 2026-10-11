import { expect, test } from "@playwright/test";

import { adminUser, seedSession, stubApi, sampleDocument } from "./helpers.js";

test.describe("File upload", () => {
  test("uploads a file via the knowledge base page and shows it in the list", async ({ page }) => {
    await seedSession(page, adminUser);
    await stubApi(page, { documents: [sampleDocument] });

    // Navigate to Knowledge base page via sidebar.
    await page.goto("/home");
    const sidebar = page.getByRole("complementary", { name: "Main sidebar" });
    await sidebar.getByRole("button", { name: "Knowledge base" }).click();

    // Wait for the knowledge base page to load (use heading for uniqueness).
    await expect(page.getByRole("heading", { name: /onboarding manual/i })).toBeVisible({ timeout: 10_000 });

    // The existing document should be visible.
    await expect(page.getByText("handbook.pdf")).toBeVisible({ timeout: 5_000 });

    // Upload a new file using the file input.
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "test-document.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("fake pdf content"),
    });

    // Upload feedback belongs to the queue; no global success toast is shown.
    const uploadStatus = page.getByRole("region", { name: "File upload status" });
    await expect(uploadStatus.getByText("test-document.pdf")).toBeVisible();
    await expect(uploadStatus.getByText("Uploaded; processing is starting")).toBeVisible();
    await expect(page.getByText(/file uploaded successfully|با موفقیت بارگذاری/i)).toHaveCount(0);
  });

  test("shows drag-and-drop zone on the knowledge base page", async ({ page }) => {
    await seedSession(page, adminUser);
    await stubApi(page, { documents: [] });

    await page.goto("/home");
    const sidebar = page.getByRole("complementary", { name: "Main sidebar" });
    await sidebar.getByRole("button", { name: "Knowledge base" }).click();

    // Wait for KB page to load first.
    await expect(page.getByRole("heading", { name: /onboarding manual/i })).toBeVisible({ timeout: 10_000 });

    // The dropzone should be visible for users who can edit the set.
    await expect(page.getByText("Drop files into this set")).toBeVisible({ timeout: 10_000 });
  });
});
