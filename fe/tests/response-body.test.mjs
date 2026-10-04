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

test("UTF-8 CSV responses remain downloadable blobs and errors remain JSON", async () => {
  const response = new Response("Actor\r\nJosé 李\r\n", { headers: { "content-type": "text/csv; charset=utf-8" } });
  const body = await parseResponseBody(response);
  assert.ok(body instanceof Blob);
  assert.equal(await body.text(), "Actor\r\nJosé 李\r\n");
  const failure = new Response('{"error":{"code":"privacy_activity_export_too_large"}}', { status: 422, headers: { "content-type": "application/json" } });
  assert.equal((await parseResponseBody(failure)).error.code, "privacy_activity_export_too_large");
});
