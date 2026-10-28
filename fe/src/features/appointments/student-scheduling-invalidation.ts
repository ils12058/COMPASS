import type { Query, QueryClient } from "@tanstack/react-query";
import { getAppointmentsListBookableSlotsQueryKey } from "@/lib/api/generated/appointments/appointments";
import { getGroupSessionsDiscoverQueryKey } from "@/lib/api/generated/group-sessions/group-sessions";
import { getServicesListBookableSlotsQueryKey } from "@/lib/api/generated/services/services";

// The generated fixed-slot key contains a Service ID; a Student commitment can affect slots
// for every Service, so invalidate that query family without invalidating the whole cache.
const [fixedPrefix, fixedSuffix] = getServicesListBookableSlotsQueryKey("__service__")[0].split("__service__");
export function isStudentFixedSlotsQuery(query: Pick<Query, "queryKey">): boolean {
  const path = query.queryKey[0];
  return typeof path === "string" && path.startsWith(fixedPrefix) && path.endsWith(fixedSuffix);
}

export function invalidateStudentScheduling(client: Pick<QueryClient, "invalidateQueries">) {
  return Promise.all([
    client.invalidateQueries({ queryKey: getAppointmentsListBookableSlotsQueryKey() }, { throwOnError: true }),
    client.invalidateQueries({ queryKey: getGroupSessionsDiscoverQueryKey() }, { throwOnError: true }),
    client.invalidateQueries({ predicate: isStudentFixedSlotsQuery }, { throwOnError: true }),
  ]);
}
