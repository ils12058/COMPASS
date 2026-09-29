export async function parseResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205 || !response.body) {
    return undefined;
  }

  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  const mimeType = contentType.split(";", 1)[0].trim();
  if (mimeType === "application/json" || mimeType.endsWith("+json")) {
    const text = await response.text();
    return text.length > 0 ? JSON.parse(text) : undefined;
  }

  if (
    mimeType.startsWith("text/") ||
    mimeType === "application/xml" ||
    mimeType.endsWith("+xml")
  ) {
    return response.text();
  }

  return response.blob();
}
