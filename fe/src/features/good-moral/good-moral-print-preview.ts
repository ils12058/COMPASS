// Called only from a direct click, after the authenticated issued PDF is available. The browser's
// native PDF viewer owns printing; opening it cannot prove a dialog or paper print completed.
export function openGoodMoralPrintPreview(blob: Blob): boolean {
  const url = URL.createObjectURL(blob);
  let preview: Window | null;
  try {
    preview = window.open(url, "_blank");
    if (!preview) {
      URL.revokeObjectURL(url);
      return false;
    }
    preview.opener = null;
  } catch {
    URL.revokeObjectURL(url);
    return false;
  }

  // An external PDF tab must keep its own URL after the request page unmounts. Release only once
  // that tab closes, so delayed viewer loading, cancelling Print, and reprinting remain possible.
  const cleanup = window.setInterval(() => {
    if (preview.closed) {
      window.clearInterval(cleanup);
      URL.revokeObjectURL(url);
    }
  }, 1000);
  return true;
}
