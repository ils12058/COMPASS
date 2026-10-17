// Synthetic portal list records. This suite checks responsive collection tables, filter states,
// and screenshots without contacting production services or using real student information.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { appointment as baseAppointment, service as baseService, slip, user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness("portal-collections");
const staff = {
  ...user(),
  capabilities: [...user().capabilities, "referrals.view", "referrals.manage"],
};
const service = {
  ...baseService,
  name: "Wellbeing Consultation",
  description: "Meet with a counselor to discuss wellbeing, study pressures, or next steps.",
};
const appointment = {
  ...baseAppointment,
  id: "appointment-collections-test",
  reference_code: "APT-TEST-026",
  student: { id: "student-example", institutional_id: "SYN-001", display_name: "Alex Example" },
  service: { ...service, id: baseService.id },
  provider: { id: "counselor-example", display_name: "Counselor Example" },
  starts_at: "2026-10-20T02:00:00Z",
  ends_at: "2026-10-20T03:00:00Z",
};
const referral = {
  id: "referral-collections-test",
  reference_code: "REF-TEST-2026-014",
  student: appointment.student,
  student_name_snapshot: appointment.student.display_name,
  course_year_block_snapshot: "BS Information Technology · 4th Year",
  referred_on: "2026-10-14",
  received_at: "2026-10-15T02:30:00Z",
  status_note: "Waiting for the initial review.",
  voided_at: null,
  form_revision: { id: "revision", official_code: "UCN-REF-01", official_revision: "1" },
};
const callSlip = {
  ...slip,
  id: "call-slip-collections-test",
  student: appointment.student,
  student_name_snapshot: appointment.student.display_name,
  student_institutional_id: appointment.student.institutional_id,
  referral: { id: referral.id, reference_code: referral.reference_code },
};
const session = {
  user: staff,
  session: { id: "ux-p2b-synthetic", expires_at: "2099-01-01T00:00:00Z", is_current: true },
};
const page = (items, ordering) => ({
  items,
  page: 1,
  page_size: 20,
  has_next: items.length > 0,
  ...(ordering ? { ordering } : {}),
});
const overrides = {
  "/api/v1/auth/session": session,
  "/api/v1/appointments": ({ reply, url }) => reply(page(
    url.searchParams.get("search") === "no-match" ? [] : [appointment],
    url.searchParams.get("ordering") ?? "EARLIEST_START",
  )),
  "/api/v1/referrals": ({ reply, url }) => reply({
    ...page(
      url.searchParams.get("search") === "no-match"
        ? []
        : [url.searchParams.get("include_voided") === "true"
          ? { ...referral, voided_at: "2026-10-15T03:00:00Z" }
          : referral],
      url.searchParams.get("ordering") ?? "NEWEST_REFERRED",
    ),
    filter_options: { form_revisions: [referral.form_revision] },
  }),
  "/api/v1/call-slips": ({ reply, url }) => reply({
    ...page(url.searchParams.get("search") === "no-match" ? [] : [callSlip], url.searchParams.get("ordering") ?? "LATEST_REPORT"),
    filter_options: { form_revisions: [referral.form_revision] },
  }),
  "/api/v1/services": ({ reply, url }) => reply(page(
    url.searchParams.get("search") === "no-match" ? [] : [service],
    url.searchParams.get("ordering") ?? "NAME_ASC",
  )),
};

const collections = [
  { name: "appointments", route: "/portal/appointments/manage", region: "Managed appointments", identityHeader: 1 },
  { name: "referrals", route: "/portal/referrals", region: "Referrals", identityHeader: 0 },
  { name: "call-slips", route: "/portal/call-slips", region: "Call Slips", identityHeader: 0 },
  { name: "service-catalog", route: "/portal/services", region: null, identityHeader: null },
];

for (const collection of collections) {
  await check(`${collection.name}-responsive-collections`, collection.route, {
    viewport: { width: 1440, height: 1000 },
    overrides,
  }, async (page) => {
    await shown(page.getByRole("heading", { level: 1 }));
    if (collection.name === "service-catalog") {
      await shown(page.getByRole("link", { name: "Wellbeing Consultation", exact: true }));
    } else {
      await shown(page.locator("tbody tr").first());
    }
    await noHorizontalOverflow(page);
    await screenshot(page, `${collection.name}-desktop-1440`);

    if (collection.name === "appointments") {
      const selection = page.getByRole("checkbox", { name: "Select APT-TEST-026", exact: true });
      await selection.check();
      await shown(page.getByText("1 selected", { exact: true }));
      await shown(page.getByRole("button", { name: "Send reminders", exact: true }));
      await page.getByRole("button", { name: "Clear selection", exact: true }).click();
      await shown(page.getByRole("button", { name: /Date and time.*Sort latest start first/ }));
    } else if (collection.name === "referrals") {
      await shown(page.getByRole("button", { name: /Referred.*Sort oldest referred first/ }));
    } else if (collection.name === "call-slips") {
      await shown(page.getByRole("button", { name: /Report.*Sort earliest report time first/ }));
    } else {
      assert.equal(await page.getByLabel("Sort", { exact: true }).inputValue(), "NAME_ASC");
    }

    const region = collection.region
      ? page.getByRole("region", { name: new RegExp(`${collection.region}.*Scroll horizontally`) })
      : null;
    for (const width of [320, 375, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: width < 400 ? 844 : 1000 });
      await noHorizontalOverflow(page);
      if (width === 375) await screenshot(page, `${collection.name}-mobile-375`);
      if (width === 1024) await screenshot(page, `${collection.name}-narrow-desktop-1024`);
      if (region && width >= 768) {
        await shown(region);
        await shown(region.getByText("Scroll horizontally to see all columns.", { exact: true }));
        await region.focus();
        assert.equal(await region.evaluate((element) => element === document.activeElement), true);
        if (width === 768) {
          const identity = region.locator("thead th").nth(collection.identityHeader);
          assert.equal(await identity.evaluate((element) => getComputedStyle(element).position), "sticky");
          await region.evaluate((element) => { element.scrollLeft = 0; });
          await page.keyboard.press("ArrowRight");
          assert.ok(await region.evaluate((element) => element.scrollLeft > 0), "The table scrolls horizontally from the keyboard");
          await page.keyboard.press("ArrowLeft");
          assert.equal(await region.evaluate((element) => element.scrollLeft), 0, "The table scrolls back horizontally from the keyboard");
          await region.evaluate((element) => element.blur());
        }
      }
    }
  });
}

await check("referrals-applied-filter", "/portal/referrals?include_voided=true", {
  viewport: { width: 1440, height: 1000 }, overrides,
}, async (page) => {
  const filters = page.getByRole("button", { name: /Filters.*1 in use/ });
  await shown(filters);
  await shown(page.getByText("Voided", { exact: true }).last());
  await screenshot(page, "referrals-applied-filter-1440");
  await filters.click();
  await shown(page.getByRole("dialog", { name: "Filters", exact: true }));
  await shown(page.getByLabel("Include voided", { exact: true }));
  await screenshot(page, "referrals-applied-filter-panel-1440");
});

await check("service-catalog-no-results", "/portal/services?search=no-match", {
  viewport: { width: 375, height: 844 }, overrides,
}, async (page) => {
  await shown(page.getByText("No services match the current search or filters.", { exact: true }));
  await noHorizontalOverflow(page);
  await screenshot(page, "service-catalog-no-results-375");
  await page.getByRole("button", { name: "Filters", exact: true }).click();
  const filterDialog = page.getByRole("dialog", { name: "Filters", exact: true });
  await shown(filterDialog);
  await shown(filterDialog.getByRole("button", { name: "Clear filters", exact: true }));
});

await check("student-call-slips-list", "/portal/call-slips", {
  role: "STUDENT",
  viewport: { width: 375, height: 844 },
  overrides: {
    ...overrides,
    "/api/v1/auth/session": {
      user: user("STUDENT"),
      session: { id: "ux-p2b-student-synthetic", expires_at: "2099-01-01T00:00:00Z", is_current: true },
    },
    "/api/v1/call-slips/me": ({ reply, url }) => reply(page([callSlip], url.searchParams.get("ordering"))),
  },
}, async (page) => {
  await shown(page.getByRole("heading", { name: "My Call Slips", exact: true }));
  await shown(page.getByRole("link", { name: /Call Slip for/ }));
  await noHorizontalOverflow(page);
  await screenshot(page, "student-call-slips-mobile-375");
});

await finish();
