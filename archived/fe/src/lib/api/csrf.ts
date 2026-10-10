const CSRF_ENDPOINT = "/api/v1/auth/csrf";

let csrfToken: string | null = null;
let csrfBootstrap: Promise<string> | null = null;

type CsrfPayload = {
  csrf_token?: unknown;
};

async function bootstrapCsrfToken(): Promise<string> {
  const response = await fetch(CSRF_ENDPOINT, {
    method: "GET",
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error("Unable to initialize request security.");
  }

  const payload = (await response.json()) as CsrfPayload;
  if (typeof payload.csrf_token !== "string" || !payload.csrf_token) {
    throw new Error("The request security token was not returned.");
  }

  csrfToken = payload.csrf_token;
  return csrfToken;
}

export async function getCsrfToken(): Promise<string> {
  if (csrfToken) {
    return csrfToken;
  }

  if (!csrfBootstrap) {
    csrfBootstrap = bootstrapCsrfToken().finally(() => {
      csrfBootstrap = null;
    });
  }

  return csrfBootstrap;
}

export function clearCsrfToken(): void {
  csrfToken = null;
}
