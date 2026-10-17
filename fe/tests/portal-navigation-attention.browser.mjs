// Browser tests and visual verification for role-aware sidebar attention badges (NAV-1)
import assert from "node:assert/strict";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { messagesAccount, sessionFor } from "./support/guidance-messages-fixtures.mjs";

const { artifacts, check, shown, finish } = await createBrowserHarness("portal-navigation-attention");

const instant = "2026-10-15T00:00:00Z";


function createAttentionMockState(role = "COUNSELOR") {
  const account = messagesAccount(role);
  const handler = async ({ pathname, reply }) => {
    if (pathname === "/api/v1/auth/session") {
      await reply(sessionFor(account));
      return true;
    }
    if (pathname === "/api/v1/guidance-operations") {
      await reply({
        generated_at: instant,
        backlog: {
          guidance_messages: { count: 1, oldest_waiting_since: instant },
          routine_evaluations: { count: 1, oldest_waiting_since: instant },
          good_moral_preparation: { count: 1, oldest_waiting_since: instant },
          good_moral_issuance: { count: 1, oldest_waiting_since: instant },
          call_slips_due: { count: 1, oldest_due_at: instant },
        },
        schedule: {
          upcoming_self_appointments_count: 2,
          upcoming_managed_appointments_count: 3,
          active_call_slips_count: 4,
        },
      });
      return true;
    }
    if (pathname === "/api/v1/guidance-messages/unread-count") {
      await reply({ unread_conversations_count: 3 });
      return true;
    }
    if (pathname === "/api/v1/work") {
      await reply({ items: [], page: 1, page_size: 20, has_next: false, generated_at: instant });
      return true;
    }
    if (pathname === "/api/v1/overview") {
      await reply({
        generated_at: instant,
        student: null,
        platform: null,
        guidance: {
          upcoming_self_appointments_count: 2,
          upcoming_managed_appointments_count: 3,
          routine_evaluation_pending_count: 1,
          good_moral_requested_count: 1,
          good_moral_ready_count: 1,
          active_call_slip_count: 1,
        },
      });
      return true;
    }
    return false;
  };
  return { handler, options: (extra = {}) => ({ handler, role, ...extra }) };
}


// 1. Desktop expanded sidebar
const stateDesktop = createAttentionMockState("COUNSELOR");
await check("Desktop expanded sidebar renders attention badges", "/portal/work", stateDesktop.options({ viewport: { width: 1440, height: 900 } }), async (page) => {
  const aside = page.locator("aside");
  await shown(aside);
  const corners = await aside.evaluate((element) => ({
    topLeft: getComputedStyle(element).borderTopLeftRadius,
    topRight: getComputedStyle(element).borderTopRightRadius,
    bottomRight: getComputedStyle(element).borderBottomRightRadius,
  }));
  assert.deepEqual(corners, { topLeft: "0px", topRight: "8px", bottomRight: "8px" });

  // My work link with badge count 5 and accessible label
  const myWorkLink = aside.getByRole("link", { name: "My work, 5 items requiring attention" });
  await shown(myWorkLink);
  const myWorkBadge = myWorkLink.locator("span", { hasText: "5" });
  await shown(myWorkBadge);

  // Messages link with badge count 3 and accessible label
  const messagesLink = aside.getByRole("link", { name: "Messages, 3 unread conversations" });
  await shown(messagesLink);
  const messagesBadge = messagesLink.locator("span", { hasText: "3" });
  await shown(messagesBadge);

  // Appointments link has NO badge
  const appointmentsLink = aside.getByRole("link", { name: "Appointments", exact: true });
  await shown(appointmentsLink);
  assert.equal(await appointmentsLink.locator("span:has-text('3')").count(), 0);

  // Capture screenshot of expanded sidebar
  const screenshotPath = join(artifacts, "nav-badges-desktop-expanded.png");
  await page.screenshot({ path: screenshotPath });
  console.log(`Saved screenshot: ${screenshotPath}`);
});

// 2. Desktop collapsed rail
const stateCollapsed = createAttentionMockState("COUNSELOR");
await check("Desktop collapsed rail renders badge chips with pointer-events-none", "/portal/work", stateCollapsed.options({ viewport: { width: 1440, height: 900 } }), async (page) => {
  // Click collapse button
  const collapseButton = page.getByRole("button", { name: "Collapse navigation" });
  await shown(collapseButton);
  await collapseButton.click();

  // Wait for collapse transition
  await page.waitForTimeout(300);

  const aside = page.locator("aside");
  assert.equal(await aside.evaluate((element) => Math.round(element.getBoundingClientRect().width)), 76, "collapsed dock keeps its icon rail width");
  const myWorkLink = aside.getByRole("link", { name: "My work, 5 items requiring attention" });
  await shown(myWorkLink);

  const messagesLink = aside.getByRole("link", { name: "Messages, 3 unread conversations" });
  await shown(messagesLink);

  await myWorkLink.focus();
  const tip = page.locator("div.fixed[aria-hidden='true']").filter({ hasText: "My work" });
  await shown(tip);
  const tipVisibleOutsideDock = await tip.evaluate((element) => {
    const tipBox = element.getBoundingClientRect();
    const dockBox = document.querySelector("aside").getBoundingClientRect();
    const hit = document.elementFromPoint(tipBox.left + tipBox.width / 2, tipBox.top + tipBox.height / 2);
    return tipBox.left >= dockBox.right && Boolean(hit && element.contains(hit));
  });
  assert.equal(tipVisibleOutsideDock, true, "the focused rail label is visible outside the dock's rounded clip");

  // Capture screenshot of collapsed rail
  const screenshotPath = join(artifacts, "nav-badges-desktop-collapsed.png");
  await page.screenshot({ path: screenshotPath });
  console.log(`Saved screenshot: ${screenshotPath}`);
});

// 3. Mobile navigation drawer
const stateMobile = createAttentionMockState("COUNSELOR");
await check("Mobile drawer renders badges in navigation items", "/portal/work", stateMobile.options({ viewport: { width: 390, height: 844 }, mobile: true }), async (page) => {
  // Open mobile drawer
  const menuButton = page.getByRole("button", { name: "Open portal navigation" });
  await shown(menuButton);
  await menuButton.click();

  const dialog = page.getByRole("dialog");
  await shown(dialog);
  assert.equal(await dialog.evaluate((element) => getComputedStyle(element).borderTopRightRadius), "0px", "mobile drawer remains square-edged");

  const myWorkLink = dialog.getByRole("link", { name: "My work, 5 items requiring attention" });
  await shown(myWorkLink);
  const myWorkBadge = myWorkLink.locator("span", { hasText: "5" });
  await shown(myWorkBadge);

  const messagesLink = dialog.getByRole("link", { name: "Messages, 3 unread conversations" });
  await shown(messagesLink);
  const messagesBadge = messagesLink.locator("span", { hasText: "3" });
  await shown(messagesBadge);

  // Capture screenshot of mobile drawer
  const screenshotPath = join(artifacts, "nav-badges-mobile-drawer.png");
  await page.screenshot({ path: screenshotPath });
  console.log(`Saved screenshot: ${screenshotPath}`);
});

await finish();
