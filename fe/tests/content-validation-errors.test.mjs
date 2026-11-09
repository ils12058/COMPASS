import assert from "node:assert/strict";
import { test } from "node:test";

import { CompassApiError } from "../src/lib/api/errors.ts";
import { resourceErrorMessage } from "../src/features/resources/resource-errors.ts";
import { announcementErrorMessage } from "../src/features/announcements/announcement-errors.ts";
import { privacyErrorMessage } from "../src/features/privacy-governance/privacy-governance-errors.ts";

const fallback = "Review the form and try again.";
const apiError = (code, details, message) => new CompassApiError({
  status: code === "resource_conflict" ? 409 : 422,
  body: { error: { code, message, details } },
  headers: {}, method: "POST", url: "/api/v1/synthetic",
});
const cases = [
  [resourceErrorMessage, "invalid_resource_input", "external_url_required", "Enter the link address before publishing this Resource."],
  [resourceErrorMessage, "invalid_resource_input", "pdf_signature_invalid", "Choose a valid PDF file."],
  [resourceErrorMessage, "invalid_resource_input", "display_order_integer_required", "Enter a whole number for the display order."],
  [resourceErrorMessage, "resource_conflict", "attached_file_kind_immutable", "Remove or replace this draft Resource to use a different type."],
  [resourceErrorMessage, "resource_conflict", "file_attachment_requires_draft", "You can attach or replace a file only while the Resource is a draft."],
  [resourceErrorMessage, "resource_conflict", "published_kind_immutable", "You can't change the type of a published Resource."],
  [announcementErrorMessage, "invalid_announcement_input", "title_too_long", "Keep the title to 200 characters or fewer."],
  [announcementErrorMessage, "invalid_announcement_input", "body_required", "Add body text before publishing this Announcement."],
  [announcementErrorMessage, "invalid_announcement_input", "expiry_not_future", "Choose a future expiry time, or archive this Announcement to remove it now."],
  [announcementErrorMessage, "announcement_not_editable", "announcement_archived", "You can't edit an archived Announcement."],
  [privacyErrorMessage, "invalid_privacy_governance_input", "audiences_required", "Choose at least one audience and no more than three."],
  [privacyErrorMessage, "invalid_privacy_governance_input", "audiences_duplicate", "Choose each audience only once."],
  [privacyErrorMessage, "invalid_privacy_governance_input", "code_invalid", "Use 2–64 letters, digits, dots, underscores or hyphens, starting with a letter or digit."],
  [privacyErrorMessage, "invalid_privacy_governance_input", "summary_too_long", "Keep the summary to 2,000 characters or fewer."],
];
for (const [mapError, code, identifier, expected] of cases) {
  test(`${mapError.name}/${identifier}: identifier survives changed and missing English text`, () => {
    for (const wording of ["First backend wording", "Rewritten backend wording", undefined]) {
      const error = apiError(code, [{ type: identifier, loc: ["ignored"], message: wording }], wording);
      assert.equal(mapError(error, fallback), expected);
    }
  });
}
for (const [mapError, code, unknownFallback] of [
  [resourceErrorMessage, "invalid_resource_input", fallback],
  [announcementErrorMessage, "invalid_announcement_input", fallback],
  [privacyErrorMessage, "invalid_privacy_governance_input", "Review the privacy record details and try again."],
]) {
  test(`${mapError.name}: unknown or malformed identifiers use safe copy`, () => {
    for (const details of [undefined, null, {}, [], [null], ["bad"], [{ type: 1 }], [{ type: "__proto__" }], [{ type: "constructor" }], [{ type: "future_validation_case", message: "PRIVATE-DIAGNOSTIC" }]]) {
      assert.equal(mapError(apiError(code, details, "title is too long"), fallback), unknownFallback);
    }
  });
  test(`${mapError.name}: familiar English without an identifier never selects a field message`, () => {
    assert.equal(mapError(apiError(code, undefined, "title is too long"), fallback), unknownFallback);
  });
  test(`${mapError.name}: an unfamiliar envelope code cannot select field copy`, () => {
    assert.equal(mapError(apiError("future_unknown_code", [{ type: "title_too_long" }]), fallback), fallback);
  });
}

test("all documented domain identifiers have frontend copy", async () => {
  const { readFile } = await import("node:fs/promises");
  const contract = JSON.parse(await readFile(new URL("../../contracts/openapi.json", import.meta.url), "utf8"));
  const operations = Object.values(contract.paths).flatMap((path) => Object.values(path));
  for (const [operationId, mapError, code] of [
    ["resourcesCreateDraft", resourceErrorMessage, "invalid_resource_input"],
    ["announcementsCreateDraft", announcementErrorMessage, "invalid_announcement_input"],
    ["privacyGovernanceCreateNotice", privacyErrorMessage, "invalid_privacy_governance_input"],
  ]) {
    const operation = operations.find((operation) => operation.operationId === operationId);
    assert.ok(operation?.["x-domain-validation-issues"]);
    for (const identifier of Object.keys(operation["x-domain-validation-issues"])) {
      const text = mapError(apiError(code, [{ type: identifier }]), fallback);
      assert.notEqual(text, fallback, identifier);
      assert.doesNotMatch(text, /Unfamiliar backend wording/);
    }
  }
});


test("privacy framework validation hides unknown and prototype field names", () => {
  for (const details of [[null], [{ loc: ["constructor"] }], [{ loc: ["__proto__"] }], [{ loc: ["internal_key_material"] }]]) {
    assert.equal(privacyErrorMessage(apiError("validation_error", details), fallback), "Review the form values and try again.");
  }
});
