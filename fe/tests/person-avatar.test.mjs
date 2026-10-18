import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { PersonAvatar, personInitials, personPhotoKey } from "../src/features/account/components/person-avatar.tsx";

test("person initials use the first and last names and handle common name formats", () => {
  assert.equal(personInitials("Juan Dela Cruz"), "JD");
  assert.equal(personInitials("Maria Santos"), "MS");
  assert.equal(personInitials("Dr. Maria Santos"), "MS");
  assert.equal(personInitials("Juan Dela Cruz, PhD"), "JD");
  assert.equal(personInitials("Cher"), "C");
  assert.equal(personInitials(""), "?");
});

test("person avatars keep the name as text and fall back to initials without a photo", () => {
  const html = renderToStaticMarkup(createElement(PersonAvatar, { displayName: "Maria Santos" }));
  assert.match(html, /aria-hidden="true"/);
  assert.match(html, />MS<\/span>/);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /size-10/);
});

test("uploaded photo URLs are rendered directly and timestamped for replacement refresh", () => {
  const html = renderToStaticMarkup(createElement(PersonAvatar, {
    displayName: "Maria Santos",
    photoUrl: "https://signed.example.test/photo?signature=synthetic",
    photoUpdatedAt: "2026-10-17T00:00:00Z",
    size: "large",
  }));
  assert.match(html, /src="https:\/\/signed\.example\.test\/photo\?signature=synthetic"/);
  assert.match(html, /alt=""/);
  assert.match(html, /size-\[4\.5rem\]/);
  const oldPhoto = personPhotoKey("https://signed.example.test/old", "2026-10-16T00:00:00Z");
  assert.notEqual(personPhotoKey("https://signed.example.test/new", "2026-10-17T00:00:00Z"), oldPhoto);
  assert.notEqual(personPhotoKey("https://signed.example.test/old", "2026-10-17T00:00:00Z"), oldPhoto);
  assert.equal(personPhotoKey(null, "2026-10-17T00:00:00Z"), null, "Removing a photo switches back to initials");
});
