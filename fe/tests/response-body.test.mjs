import assert from "node:assert/strict";
import { test } from "node:test";

import { parseResponseBody } from "../src/lib/api/response-body.ts";

test("XLSX responses stay binary despite openxmlformats in the MIME type", async () => {
  const response = new Response(new Uint8Array([0x50, 0x4b, 0x03, 0x04]), {
    headers: {
      "content-type":
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
  });

  const body = await parseResponseBody(response);

  assert.ok(body instanceof Blob);
  assert.deepEqual([...new Uint8Array(await body.arrayBuffer())], [0x50, 0x4b, 0x03, 0x04]);
});

test("actual XML and JSON responses retain their structured parsing", async () => {
  const xml = new Response("<root />", {
    headers: { "content-type": "application/atom+xml; charset=utf-8" },
  });
  const json = new Response('{"ok":true}', {
    headers: { "content-type": "application/json; charset=utf-8" },
  });

  assert.equal(await parseResponseBody(xml), "<root />");
  assert.deepEqual(await parseResponseBody(json), { ok: true });
});
