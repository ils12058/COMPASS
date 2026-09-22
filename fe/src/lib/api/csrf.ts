const CSRF_BOOTSTRAP_PATH = "/api/v1/auth/csrf";

let cachedToken: string | undefined;
let pendingBootstrap: Promise<string> | undefined;

async function requestCsrfToken(): Promise<string> {
  const response = await fetch(CSRF_BOOTSTRAP_PATH, {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error("Request security could not be initialized.");
  }

  const body: unknown = await response.json();
  if (
    !body ||
    typeof body !== "object" ||
    !("csrf_token" in body) ||
    typeof body.csrf_token !== "string" ||
    body.csrf_token.length === 0
  ) {
    throw new Error("The server did not return a request security token.");
  }

  cachedToken = body.csrf_token;
  return cachedToken;
}

export function clearCsrfToken() {
  cachedToken = undefined;
}

export async function getCsrfToken(): Promise<string> {
  if (cachedToken) {
    return cachedToken;
  }

  pendingBootstrap ??= requestCsrfToken().finally(() => {
    pendingBootstrap = undefined;
  });

  return pendingBootstrap;
}
