import type { QueryClient, QueryKey } from "@tanstack/react-query";
import * as api from "@/lib/api/generated/organization/organization";
import type { CatalogHistoryItem } from "@/lib/api/generated/model";
import type { CatalogCommand, CatalogKind, CatalogTarget } from "./catalog-model";

// Only dispatches generated operations/keys. No feature transport or handwritten URL contracts.
export function catalogDetailKey(kind: CatalogKind, id: string) {
  return kind === "campus" ? api.getOrganizationGetCampusQueryKey(id) : kind === "college" ? api.getOrganizationGetCollegeQueryKey(id) : api.getOrganizationGetProgramQueryKey(id);
}
export async function readCatalogTarget(kind: CatalogKind, id: string, signal?: AbortSignal): Promise<CatalogTarget> {
  if (kind === "campus") return { kind, record: (await api.organizationGetCampus(id, { signal })).data };
  if (kind === "college") return { kind, record: (await api.organizationGetCollege(id, { signal })).data };
  return { kind, record: (await api.organizationGetProgram(id, { signal })).data };
}
export function catalogImpactKey(kind: CatalogKind, id: string) {
  return kind === "campus" ? api.getOrganizationGetCampusImpactQueryKey(id) : kind === "college" ? api.getOrganizationGetCollegeImpactQueryKey(id) : api.getOrganizationGetProgramImpactQueryKey(id);
}
export async function readCatalogImpact(kind: CatalogKind, id: string, signal?: AbortSignal) {
  return (await (kind === "campus" ? api.organizationGetCampusImpact(id, { signal }) : kind === "college" ? api.organizationGetCollegeImpact(id, { signal }) : api.organizationGetProgramImpact(id, { signal }))).data;
}
export function catalogHistoryKey(kind: CatalogKind, id: string, page?: number) {
  const params = page ? { page, page_size: 10 } : undefined;
  return kind === "campus" ? api.getOrganizationGetCampusHistoryQueryKey(id, params) : kind === "college" ? api.getOrganizationGetCollegeHistoryQueryKey(id, params) : api.getOrganizationGetProgramHistoryQueryKey(id, params);
}
export async function readCatalogHistory(kind: CatalogKind, id: string, page = 1, signal?: AbortSignal) {
  const params = { page, page_size: 10 };
  return (await (kind === "campus" ? api.organizationGetCampusHistory(id, params, { signal }) : kind === "college" ? api.organizationGetCollegeHistory(id, params, { signal }) : api.organizationGetProgramHistory(id, params, { signal }))).data;
}
export async function executeCatalogCommand(command: CatalogCommand): Promise<CatalogTarget> {
  switch (command.operation) {
    case "createCampus": return { kind: "campus", record: (await api.organizationCreateCampus(command.data)).data };
    case "createCollege": return { kind: "college", record: (await api.organizationCreateCollege(command.data)).data };
    case "createProgram": return { kind: "program", record: (await api.organizationCreateProgram(command.data)).data };
    case "policy": return { kind: "program", record: (await api.organizationUpdateProgramPolicy(command.target.record.id, command.data)).data };
    case "rename": {
      const { target, data } = command;
      if (target.kind === "campus") return { kind: target.kind, record: (await api.organizationRenameCampus(target.record.id, data)).data };
      if (target.kind === "college") return { kind: target.kind, record: (await api.organizationRenameCollege(target.record.id, data)).data };
      return { kind: target.kind, record: (await api.organizationRenameProgram(target.record.id, data)).data };
    }
    case "status": {
      const { target, data } = command;
      if (target.kind === "campus") return { kind: target.kind, record: (await api.organizationSetCampusActive(target.record.id, data)).data };
      if (target.kind === "college") return { kind: target.kind, record: (await api.organizationSetCollegeActive(target.record.id, data)).data };
      return { kind: target.kind, record: (await api.organizationSetProgramActive(target.record.id, data)).data };
    }
  }
}
export async function refreshCatalog(queryClient: QueryClient, target?: CatalogTarget) {
  // These three unpaginated collections also back current-use selectors with parameter variants.
  const keys: QueryKey[] = [api.getOrganizationListCampusesQueryKey(), api.getOrganizationListCollegesQueryKey(), api.getOrganizationListProgramsQueryKey()];
  if (target) keys.push(catalogDetailKey(target.kind, target.record.id), catalogImpactKey(target.kind, target.record.id), catalogHistoryKey(target.kind, target.record.id));
  await Promise.all(keys.map((queryKey) => queryClient.invalidateQueries({ queryKey }, { throwOnError: true })));
}

export function historyConfirmsCommand(command: CatalogCommand, item: CatalogHistoryItem, actorId: string) {
  if (item.actor_id !== actorId || item.basis !== command.data.basis) return false;
  if (command.operation === "createCampus" || command.operation === "createCollege" || command.operation === "createProgram") {
    if (item.resource_version_before !== null || item.resource_version_after !== 1 || item.code !== command.data.code || !item.action.endsWith(".created")) return false;
    if (command.operation === "createCollege" && item.parent_id !== command.data.campus_id) return false;
    if (command.operation === "createProgram" && item.parent_id !== command.data.college_id) return false;
    if (item.after.name !== command.data.name || item.after.is_active !== command.data.is_active) return false;
    return command.operation !== "createProgram" || (item.after.academic_classification === command.data.academic_classification && item.after.year_level_policy_status === command.data.year_level_policy_status && JSON.stringify(item.after.applicable_year_levels) === JSON.stringify(command.data.applicable_year_levels));
  }
  if (item.resource_version_before !== command.data.expected_resource_version || item.resource_version_after !== command.data.expected_resource_version + 1) return false;
  if (command.operation === "rename") return item.action.endsWith(".updated") && item.after.name === command.data.name;
  if (command.operation === "status") return item.action.endsWith(command.data.is_active ? ".enabled" : ".disabled") && item.after.is_active === command.data.is_active;
  return item.action.endsWith(".policy_changed") && item.after.academic_classification === command.data.academic_classification && item.after.year_level_policy_status === command.data.year_level_policy_status && JSON.stringify(item.after.applicable_year_levels) === JSON.stringify(command.data.applicable_year_levels);
}

export async function reconcileCatalogCommand(command: CatalogCommand, actorId: string, knownIds: readonly string[]): Promise<CatalogTarget | null> {
  let target: CatalogTarget | undefined;
  if ("target" in command) target = await readCatalogTarget(command.target.kind, command.target.record.id);
  else if (command.operation === "createCampus") {
    const match = (await api.organizationListCampuses({})).data.items.find((item) => item.code === command.data.code && !knownIds.includes(item.id));
    if (match) target = { kind: "campus", record: match };
  } else if (command.operation === "createCollege") {
    const match = (await api.organizationListColleges({})).data.items.find((item) => item.code === command.data.code && item.campus.id === command.data.campus_id && !knownIds.includes(item.id));
    if (match) target = { kind: "college", record: match };
  } else {
    const match = (await api.organizationListPrograms({})).data.items.find((item) => item.code === command.data.code && item.college.id === command.data.college_id && !knownIds.includes(item.id));
    if (match) target = { kind: "program", record: match };
  }
  if (!target) return null;
  const history = await readCatalogHistory(target.kind, target.record.id);
  const event = history.items.find((item) => historyConfirmsCommand(command, item, actorId));
  if (!event) return null;
  // A commit can land between the first detail read and history read. Re-read rather than
  // presenting the older detail response as the confirmed saved state.
  const latest = await readCatalogTarget(target.kind, target.record.id);
  return latest.record.resource_version >= event.resource_version_after ? latest : null;
}
