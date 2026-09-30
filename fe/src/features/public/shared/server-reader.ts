import "server-only";

import { cache } from "react";
import { headers } from "next/headers";

import {
  announcementsGetPublic,
  announcementsGetVisible,
} from "@/lib/api/generated/announcements/announcements";
import {
  resourcesGetPublic,
  resourcesGetVisible,
} from "@/lib/api/generated/resources/resources";
import { CompassApiError } from "@/lib/api/errors";

export type ServerReaderResolution =
  | { kind: "available"; title: string; indexable: boolean }
  | { kind: "not-found" }
  | { kind: "unresolved" };

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isReaderUuid(value: string): boolean {
  return UUID_PATTERN.test(value);
}

function cookieOptions(cookieHeader: string): RequestInit {
  return {
    cache: "no-store",
    headers: {
      Accept: "application/json",
      Cookie: cookieHeader,
    },
  };
}

const publicOptions: RequestInit = {
  cache: "no-store",
  headers: { Accept: "application/json" },
};

function resultFromError(error: unknown): "unauthenticated" | "not-found" | "unresolved" {
  if (!(error instanceof CompassApiError)) return "unresolved";
  if (error.status === 401) return "unauthenticated";
  if (error.status === 404) return "not-found";
  return "unresolved";
}

async function resolveReader(
  readVisible: (options: RequestInit) => Promise<{ data: { title: string } }>,
  readPublic: (options: RequestInit) => Promise<{ data: { title: string } }>,
): Promise<ServerReaderResolution> {
  const cookieHeader = (await headers()).get("cookie");

  if (cookieHeader) {
    try {
      const response = await readVisible(cookieOptions(cookieHeader));
      let indexable = false;
      try {
        await readPublic(publicOptions);
        indexable = true;
      } catch {
        // A record readable to this account but not through the anonymous
        // reader must not become indexable merely because the request is signed in.
      }
      return { kind: "available", title: response.data.title, indexable };
    } catch (error) {
      const state = resultFromError(error);
      if (state === "not-found") return { kind: "not-found" };
      if (state !== "unauthenticated") return { kind: "unresolved" };
    }
  }

  try {
    const response = await readPublic(publicOptions);
    return { kind: "available", title: response.data.title, indexable: true };
  } catch {
    // A public 404 is deliberately ambiguous: the record may be restricted
    // content that becomes readable after sign-in. Preserve the client reader
    // fallback rather than turning that ambiguity into a route-level oracle.
    return { kind: "unresolved" };
  }
}

export const resolveAnnouncementReader = cache(
  async (announcementId: string): Promise<ServerReaderResolution> =>
    resolveReader(
      (options) => announcementsGetVisible(announcementId, options),
      (options) => announcementsGetPublic(announcementId, options),
    ),
);

export const resolveResourceReader = cache(
  async (resourceId: string): Promise<ServerReaderResolution> =>
    resolveReader(
      (options) => resourcesGetVisible(resourceId, options),
      (options) => resourcesGetPublic(resourceId, options),
    ),
);
