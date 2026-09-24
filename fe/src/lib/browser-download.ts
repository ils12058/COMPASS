type BinaryResponse = {
  data: Blob;
  headers: Record<string, string>;
};

function safeFilenameFromHeader(value: string | undefined): string | null {
  if (!value) return null;
  const extended = value.match(/filename\*\s*=\s*UTF-8''([^;]+)/i)?.[1];
  const quoted = value.match(/filename\s*=\s*"([^"]+)"/i)?.[1];
  const plain = value.match(/filename\s*=\s*([^;]+)/i)?.[1]?.trim();
  const candidate = extended ?? quoted ?? plain;
  if (!candidate) return null;

  let decoded = candidate;
  try {
    decoded = decodeURIComponent(candidate);
  } catch {
    // Keep the header value when it is not URI encoded.
  }

  const basename = decoded.split(/[\\/]/).at(-1)?.replace(/[\r\n]/g, "").trim();
  return basename || null;
}

export function downloadBinaryResponse(
  response: BinaryResponse,
  fallbackFilename: string,
): void {
  const objectUrl = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download =
    safeFilenameFromHeader(response.headers["content-disposition"]) ??
    fallbackFilename;
  anchor.hidden = true;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
