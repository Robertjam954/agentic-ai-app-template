import { expect, test } from "@playwright/test"

test("authenticated users see a clear configuration error when the agent is disabled", async ({
  page,
}) => {
  await page.goto("/agent")

  await page.getByPlaceholder("Message the agent…").fill("Hello")
  await page.getByRole("button", { name: "Send" }).click()

  await expect(
    page.getByText(
      "Agent not configured — set ANTHROPIC_API_KEY on the backend.",
    ),
  ).toBeVisible()
})

test("agent chat presents explicit privacy-safe preference controls", async ({
  page,
}) => {
  await page.goto("/agent")

  await expect(
    page.getByText(
      "Do not include patient, health, or other personal data in saved preferences.",
    ),
  ).toBeVisible()
  await expect(page.getByLabel("Preference to save")).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Save preference" }),
  ).toBeVisible()
})
