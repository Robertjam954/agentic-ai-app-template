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
