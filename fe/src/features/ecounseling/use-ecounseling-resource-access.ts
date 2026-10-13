"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import { ecounselingResourceAccess } from "./ecounseling-resource-access";

export function useECounselingResourceDenial(appointmentId: string | null) {
  const access = ecounselingResourceAccess(useQueryClient());
  return useSyncExternalStore(access.subscribe, () => access.getDenial(appointmentId), () => null);
}
