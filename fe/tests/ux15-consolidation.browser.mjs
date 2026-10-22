// Cross-pilot semantics and reflow audit. Existing pilot suites own workflow/payload coverage.
// All records are synthetic and every API is intercepted by the local browser harness.
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { exitFixture, exitPath } from "./support/ux15-exit-fixtures.mjs";
import { tracerFixture, tracerPath } from "./support/ux15-tracer-fixtures.mjs";
import { routineIntakeFixture, routineIntakePath } from "./support/ux15-routine-intake-fixtures.mjs";
import { counselorEvaluationFixture, routineEvaluationId, routineEvaluationPath } from "./support/ux15-counselor-evaluation-fixtures.mjs";
import { counselingOverview } from "./support/guidance-contextual-fixtures.mjs";

const { check, finish, shown, noHorizontalOverflow, artifacts } = await createBrowserHarness("ux15-consolidation");
const observations = [];
const captureDir = process.env.COMPASS_UX15_CONSOLIDATION_CAPTURE;
const phase = process.env.COMPASS_UX15_CONSOLIDATION_PHASE ?? "after";

function inventoryOptions() {
  const record = {
    id: "synthetic-inventory", academic_year: { id: "year", label: "2026–2027" }, status: "DRAFT", program: null,
    form_revision: { id: "revision", family_key: "individual_inventory", internal_schema_version: 1, official_code: "UCN-OP-GCO-01F5", official_revision: "1" },
    correction_pending: false, latest_correction: null, full_name: "Synthetic Student", student_number: "SYNTHETIC-01", sex: "FEMALE", date_of_birth: "2005-01-15",
    civil_status_category: "SINGLE", current_religion_category: "NONE", contact_number: "0917 000 0000", geographic_locations: [{ kind: "CURRENT", not_specified: true }],
    parent_status_category: "MARRIED", support_profile: { four_ps_status: "NOT_BENEFICIARY", indigenous_peoples_status: "NOT_MEMBER", mother_life_status: "LIVING", father_life_status: "LIVING" },
    family_members: [], living_arrangement: "OWN_HOUSE", pwd_status: "NON_PWD", year_level: 2, siblings: [], organization_memberships: [], transportation_entries: [],
  };
  return { overrides: {
    "/api/v1/auth/session": sessionFor({ ...user("STUDENT"), capabilities: ["inventory.view_self", "inventory.manage_self"] }),
    "/api/v1/inventory/me/status": record,
    "/api/v1/inventory/me/current": record,
    "/api/v1/inventory/me/history": { items: [], page: 1, page_size: 20, has_next: false },
  } };
}

const opportunityId = "bb111111-1111-4111-8111-111111111111";
function feedbackOptions(csm = false) {
  return { overrides: {
    "/api/v1/auth/session": sessionFor({ ...user("STUDENT"), capabilities: [csm ? "feedback.submit_csm" : "feedback.submit_customer_feedback"] }),
    [`/api/v1/feedback/opportunities/${opportunityId}`]: {
      id: opportunityId, service_kind: "COUNSELING", service_label: "Counseling", service_completed_at: "2026-10-14T00:00:00Z",
      customer_feedback_submitted: false, csm_submitted: false, can_submit_customer_feedback: !csm, can_submit_csm: csm,
    },
  } };
}

const experiences = [
  { name: "inventory", path: "/portal/inventory/current", heading: "inventory-editor-heading", options: inventoryOptions },
  { name: "exit", path: exitPath, heading: "exit-interview-form-heading", options: () => ({ handler: exitFixture().handler }) },
  { name: "tracer", path: tracerPath, heading: "graduate-tracer-form-heading", options: () => ({ handler: tracerFixture().handler }) },
  { name: "intake", path: routineIntakePath, heading: "routine-student-intake-heading", options: () => ({ handler: routineIntakeFixture().handler }) },
  { name: "evaluation", path: routineEvaluationPath, heading: "routine-evaluation-heading", options: () => ({ handler: counselorEvaluationFixture().handler }) },
  { name: "customer", path: `/portal/feedback/customer-feedback?opportunity=${opportunityId}`, heading: "customer-feedback-heading", options: () => feedbackOptions() },
  { name: "csm", path: `/portal/feedback/csm?opportunity=${opportunityId}`, heading: "csm-page-heading", options: () => feedbackOptions(true) },
];

for (const experience of experiences) {
  for (const [width, enlarged] of [[1440, false], [768, false], [390, false], [320, false], [1440, true], [768, true], [390, true], [320, true]]) {
    const name = `${experience.name} ${width}px${enlarged ? " 200% text" : ""}`;
    await check(name, experience.path, {
      ...experience.options(), viewport: { width, height: 1000 },
    }, async (page, fixture) => {
      const root = page.locator(`section[aria-labelledby="${experience.heading}"]`);
      await shown(page.locator(`#${experience.heading}`));
      if (enlarged) await page.addStyleTag({ content: ":root { font-size: 200% !important; }" });
      if (!enlarged) await noHorizontalOverflow(page);
      const result = await root.evaluate((element) => {
        const visible = (node) => Boolean(node.getClientRects().length);
        const descendants = [...element.querySelectorAll("*")];
        const ids = [...document.querySelectorAll("[id]")].map((node) => node.id);
        const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
        const brokenReferences = descendants.flatMap((node) => ["aria-labelledby", "aria-describedby"].flatMap((attribute) =>
          (node.getAttribute(attribute) ?? "").split(/\s+/).filter(Boolean).filter((id) => !document.getElementById(id)).map((id) => `${node.tagName}#${node.id} ${attribute}=${id}`)));
        const unlabelled = descendants.filter((node) => visible(node) && node.matches("input:not([type=hidden]), select, textarea") &&
          !node.labels?.length && !node.getAttribute("aria-label") && !node.getAttribute("aria-labelledby")).map((node) => node.id || node.name);
        const localScroll = (node) => {
          for (let parent = node.parentElement; parent && parent !== element; parent = parent.parentElement) {
            if (getComputedStyle(parent).overflowX === "auto") return true;
          }
          return false;
        };
        const overflow = descendants.filter((node) => visible(node) && node.getBoundingClientRect().right > innerWidth + 1 && !localScroll(node)).map((node) => `${node.tagName}#${node.id}`);
        const header = document.querySelector("header");
        return {
          duplicateIds, brokenReferences, unlabelled, overflow,
          pageWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth,
          rootWidth: element.clientWidth, rootScrollWidth: element.scrollWidth,
          headerWidth: header?.clientWidth, headerScrollWidth: header?.scrollWidth,
          headerControls: [...(header?.querySelectorAll("button, a") ?? [])].filter(visible).map((node) => ({ name: node.getAttribute("aria-label") || node.textContent?.trim(), right: Math.round(node.getBoundingClientRect().right) })),
        };
      });
      observations.push({ name, ...result });
      if (captureDir && experience.name === "intake" && width === 320 && enlarged) {
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: join(captureDir, `${phase}-portal-header-320-200.png`) });
      }
      if (captureDir && ((experience.name === "evaluation" && width === 320 && enlarged) || (experience.name === "exit" && width === 390 && !enlarged))) {
        const target = experience.name === "evaluation"
          ? root.getByRole("heading", { name: "Adjustment ratings", exact: true })
          : page.locator("#exit-learning-experiences");
        await target.evaluate((node) => node.scrollIntoView({ block: "start" }));
        await page.screenshot({ path: join(captureDir, `${phase}-${experience.name}-${width}${enlarged ? "-200" : ""}.png`) });
      }
      assert.deepEqual(result.duplicateIds, [], "IDs are unique");
      assert.deepEqual(result.brokenReferences, [], "Descriptions and heading references resolve");
      assert.deepEqual(result.unlabelled, [], "Native controls have accessible labels");
      assert.deepEqual(result.overflow, [], "Form reflows, apart from its intentional local matrix scrollers");
      assert.ok(result.rootScrollWidth <= result.rootWidth + 1, `Form sheet scrollWidth ${result.rootScrollWidth}px exceeds ${result.rootWidth}px`);
      if (experience.name === "exit" && !enlarged) {
        const heights = await root.locator('input[type="checkbox"]').evaluateAll((nodes) => nodes.map((node) => node.closest("label").getBoundingClientRect().height));
        assert.ok(heights.every((height) => height >= 44), `Checkbox labels keep the pilot's 44px target convention: ${heights}`);
      }
      const links = root.locator('nav a[href^="#"]');
      for (let index = 0; index < await links.count(); index++) {
        const link = links.nth(index);
        const id = (await link.getAttribute("href")).slice(1);
        await link.focus();
        await page.keyboard.press("Enter");
        assert.equal(await page.evaluate(() => document.activeElement?.id), id, "Section navigation focuses its named destination");
        assert.ok(await page.locator(`[id="${id}"]`).evaluate((node) => node.getBoundingClientRect().top >= 0), "Destination is visible");
      }
      assert.equal(fixture.requests.filter(({ method }) => ["POST", "PUT", "PATCH", "DELETE"].includes(method)).length, 0, "Audit navigation never writes");
    });
  }
}

for (const width of [1440, 320]) {
  await check(`inventory all choice targets ${width}px`, "/portal/inventory/current", {
    ...inventoryOptions(), viewport: { width, height: 1000 },
  }, async (page, fixture) => {
    await shown(page.locator("#inventory-full-name"));
    let choiceCount = 0;
    for (const [index, section] of ["personal", "family", "background", "health", "education", "interests", "organizations", "plans", "review"].entries()) {
      if (width === 320) await page.locator("#inventory-section-select").selectOption(section);
      else await page.getByRole("navigation", { name: "Individual Inventory sections", exact: true }).getByRole("button").nth(index).click();
      if (section === "background") await page.getByRole("button", { name: "Add sibling", exact: true }).click();
      if (section === "health") await page.locator("#inventory-living-arrangement").selectOption("BOARDING_HOUSE");
      const sizes = await page.locator('section[aria-labelledby="inventory-editor-heading"] fieldset input[type="radio"], section[aria-labelledby="inventory-editor-heading"] fieldset input[type="checkbox"]').evaluateAll((nodes) => nodes.map((node) => {
        const label = node.closest("label");
        return { label: label?.textContent?.trim(), height: label?.getBoundingClientRect().height };
      }));
      observations.push({ name: `inventory ${width}px ${section} choice targets`, sizes });
      if (captureDir && width === 320 && section === "family") {
        await page.getByRole("checkbox", { name: "Mother works overseas", exact: true }).evaluate((node) => node.closest("label").scrollIntoView({ block: "center" }));
        await page.screenshot({ path: join(captureDir, `${phase}-inventory-320.png`) });
      }
      choiceCount += sizes.length;
      assert.deepEqual(sizes.filter(({ height }) => height < 44), [], `${section} choice targets are at least 44px tall`);
      await noHorizontalOverflow(page);
    }
    assert.ok(choiceCount > 20, "Choice checks cover the actual section helpers");
    assert.equal(fixture.requests.filter(({ method }) => ["POST", "PUT"].includes(method)).length, 0);
  });
}

await check("finalized Evaluation 320px 200% text", routineEvaluationPath, {
  handler: counselorEvaluationFixture({ evaluationStatus: "FINALIZED" }).handler,
  viewport: { width: 320, height: 1000 },
}, async (page) => {
  const panel = page.locator('section[aria-labelledby="routine-evaluation-heading"]');
  await shown(panel);
  await page.addStyleTag({ content: ":root { font-size: 200% !important; }" });
  const dimensions = await panel.evaluate((node) => ({ width: node.clientWidth, scroll: node.scrollWidth }));
  observations.push({ name: "finalized Evaluation 320px 200% text", ...dimensions });
  assert.ok(dimensions.scroll <= dimensions.width + 1, `Read-only sheet scrollWidth ${dimensions.scroll}px exceeds ${dimensions.width}px`);
  assert.equal(await panel.locator("input, textarea, button").count(), 0, "Finalized content remains read-only");
});

for (const evaluationStatus of ["DRAFT", "FINALIZED"]) {
  const state = counselorEvaluationFixture({ evaluationStatus });
  await check(`Counseling workspace Evaluation ${evaluationStatus} 320px 200% text`, `/portal/counseling/workspace/routine-interview/${routineEvaluationId}`, {
    viewport: { width: 320, height: 1000 },
    handler: async (args) => {
      if (await state.handler(args)) return true;
      if (args.pathname === `/api/v1/counseling/context/ROUTINE_INTERVIEW/${routineEvaluationId}`) {
        await args.reply({
          ...counselingOverview({ anchorType: "ROUTINE_INTERVIEW", anchorId: routineEvaluationId }),
          routine_interview: state.detail,
        });
        return true;
      }
      return false;
    },
  }, async (page, fixture) => {
    await page.getByRole("tab", { name: "Routine Interview", exact: true }).click();
    const heading = page.getByRole("heading", { name: "Counselor Evaluation", exact: true });
    await shown(heading);
    await page.addStyleTag({ content: ":root { font-size: 200% !important; }" });
    const panel = heading.locator("xpath=../../..");
    const dimensions = await panel.evaluate((node) => ({ width: node.clientWidth, scroll: node.scrollWidth }));
    observations.push({ name: `Counseling workspace Evaluation ${evaluationStatus}`, ...dimensions });
    assert.ok(dimensions.scroll <= dimensions.width + 1, `Embedded Evaluation scrollWidth ${dimensions.scroll}px exceeds ${dimensions.width}px`);
    assert.equal(fixture.requests.filter(({ method }) => ["POST", "PUT", "PATCH", "DELETE"].includes(method)).length, 0);
  });
}

await writeFile(join(artifacts, "observations.json"), `${JSON.stringify(observations, null, 2)}\n`);
await finish();
