import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { catalogFixture } from "./support/catalog-fixtures.mjs";

const h = await createBrowserHarness("composition-help");
for (const device of ["desktop", "phone"]) {
  const fixture = catalogFixture();
  await h.check(`help-${device}`, "/portal/organization", { handler: fixture.handler, device }, async page => {
    const button = page.getByRole("button", { name: "Help: Organization structure", exact: true });
    await h.shown(button);
    const bounds = await button.boundingBox();
    assert.ok(bounds.width >= 44 && bounds.height >= 44, "Help has a touch-friendly target");
    if (device === "desktop") {
      await page.keyboard.press("Tab");
      await button.focus();
      await h.shown(page.getByRole("tooltip"));
    } else {
      await h.shown(button.getByText("Help", { exact: true }));
    }
    await button.click();
    const dialog = page.getByRole("dialog");
    await h.shown(dialog.getByRole("heading", { name: "Organization structure" }));
    await page.keyboard.press("Escape");
    await h.hidden(dialog);
    assert.equal(await button.evaluate(node => node === document.activeElement), true, "Closing Help returns focus");
  });
}
await h.finish();
