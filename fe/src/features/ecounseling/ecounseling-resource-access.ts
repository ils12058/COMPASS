import type { Mutation, Query, QueryClient, QueryKey } from "@tanstack/react-query";

import { isAuthorityError, isMutationAuthorityError } from "@/features/freshness/query-freshness";
import { CompassApiError } from "@/lib/api/errors";
import { getCounselingContextGetOverviewQueryKey, getCounselingGetEncounterQueryKey } from "@/lib/api/generated/counseling/counseling";
import { getECounselingGetAssignedWorkspaceQueryKey, getECounselingGetMyWorkspaceQueryKey } from "@/lib/api/generated/e-counseling/e-counseling";
import { getGuidanceMessagesGetAppointmentContextQueryKey, getGuidanceMessagesGetThreadQueryKey } from "@/lib/api/generated/guidance-messages/guidance-messages";
import { getRoutineInterviewsGetAssignedQueryKey, getRoutineInterviewsGetMineQueryKey } from "@/lib/api/generated/routine-interviews/routine-interviews";
import { ECounselingCaptureStatus } from "@/lib/api/generated/model";
import { confirmedAccountId } from "@/lib/query/account-ownership";
import { getAuthGetSessionQueryKey } from "@/lib/api/generated/auth/auth";

import { captureSafetyState } from "./runtime/runtime-model";

type CaptureKind = "recording" | "transcription";
export type ResourceDenial = { error: CompassApiError; captureKinds: CaptureKind[] };
type Resource = { epoch: number; denial: ResourceDenial | null; paths: Set<string>; captureKinds: CaptureKind[] };

const workspaceRoots = [getECounselingGetAssignedWorkspaceQueryKey("")[0], getECounselingGetMyWorkspaceQueryKey("")[0]];
const includesPath = (path: string, root: string) => path === root || path.startsWith(`${root}/`);
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const responseData = (value: unknown) => isRecord(value) && isRecord(value.data) ? value.data : undefined;
const idOf = (value: unknown) => isRecord(value) && typeof value.id === "string" ? value.id : null;

function ecounselingAppointment(path: unknown): string | null {
  if (typeof path !== "string") return null;
  const root = workspaceRoots.find((prefix) => path.startsWith(prefix));
  return root ? path.slice(root.length).split("/")[0] || null : null;
}

function canonicalPath(path: unknown, id: string): boolean {
  return path === getECounselingGetAssignedWorkspaceQueryKey(id)[0] || path === getECounselingGetMyWorkspaceQueryKey(id)[0];
}

// A narrow counterpart to account cache ownership: only an E-Counseling resource's known detail
// queries are concealed. The server still decides access. No record content is held here, and
// ordinary portal queries/freshness defaults are untouched.
export class ECounselingResourceAccess {
  private resources = new Map<string, Resource>();
  private listeners = new Set<() => void>();
  private reads = new WeakMap<Query, number>();
  private mutations = new WeakMap<object, { id: string; epoch: number }>();
  private editing = false;
  private owner: string | null = null;

  constructor(private client: QueryClient) {
    client.getQueryCache().subscribe((event) => {
      if (this.editing) return;
      if (event.type === "added") {
        const id = this.appointmentFor(event.query.queryKey);
        const denial = this.getDenial(id);
        if (denial && event.query.state.data !== undefined) this.conceal(event.query, denial.error);
        return;
      }
      if (event.type !== "updated") return;
      const { query, action } = event;
      if (action.type === "success" && query.queryKey[0] === getAuthGetSessionQueryKey()[0]) {
        const owner = confirmedAccountId(query.state.data);
        if (owner !== null && this.owner !== null && owner !== this.owner) {
          this.resources.clear();
          this.emit();
        }
        if (owner !== null) this.owner = owner;
        return;
      }
      const id = this.appointmentFor(query.queryKey);
      if (!id) return;
      const resource = this.resource(id);
      // TanStack also uses setState when applying initialData/reset state. It carries no fresh
      // authorization, just as a manual cache write does.
      if (action.type === "setState" && resource.denial && query.state.data !== undefined) {
        this.conceal(query, resource.denial.error);
        return;
      }
      if (action.type === "fetch") this.reads.set(query, resource.epoch);
      if (action.type === "error" && isAuthorityError(query.state.error) && ecounselingAppointment(query.queryKey[0])) {
        this.deny(id);
      } else if (action.type === "success") {
        // setQueryData, a delayed pre-denial read, or an independently successful child read cannot
        // authorize the parent. Recovery requires a new canonical GET started after the denial.
        if (resource.denial) {
          if (canonicalPath(query.queryKey[0], id) && !action.manual && this.reads.get(query) === resource.epoch) {
            resource.denial = null;
            this.rememberRelations(resource, query.state.data);
            this.emit();
            void client.invalidateQueries({ predicate: (candidate) => this.appointmentFor(candidate.queryKey) === id && !canonicalPath(candidate.queryKey[0], id) });
          } else {
            this.conceal(query, resource.denial.error);
          }
        } else {
          this.rememberRelations(resource, query.state.data);
        }
      }
    });
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };
  private emit() { for (const listener of this.listeners) listener(); }
  getDenial = (id: string | null): ResourceDenial | null => id ? this.resources.get(id)?.denial ?? null : null;
  captureWarnings(id: string | null): CaptureKind[] { return id ? this.resources.get(id)?.captureKinds ?? [] : []; }
  epoch(id: string) { return this.resource(id).epoch; }
  assertAuthorized(id: string, epoch = this.epoch(id)) {
    const resource = this.resource(id);
    if (resource.denial || resource.epoch !== epoch) throw resource.denial?.error ?? this.unavailableError(id);
  }

  private resource(id: string): Resource {
    let value = this.resources.get(id);
    if (!value) {
      value = { epoch: 0, denial: null, captureKinds: [], paths: new Set([
        getECounselingGetAssignedWorkspaceQueryKey(id)[0], getECounselingGetMyWorkspaceQueryKey(id)[0],
        getCounselingContextGetOverviewQueryKey("APPOINTMENT", id)[0],
        getGuidanceMessagesGetAppointmentContextQueryKey(id)[0],
      ]) };
      this.resources.set(id, value);
    }
    return value;
  }

  private appointmentFor(key: QueryKey): string | null {
    const direct = ecounselingAppointment(key[0]);
    if (direct) { this.resource(direct); return direct; }
    if (typeof key[0] !== "string") return null;
    const path = key[0];
    for (const [id, resource] of this.resources) if ([...resource.paths].some((root) => includesPath(path, root))) return id;
    return null;
  }

  private rememberRelations(resource: Resource, response: unknown) {
    const data = responseData(response);
    if (!data) return;
    if (isRecord(data.media)) {
      const media = data.media;
      resource.captureKinds = (["recording", "transcription"] as const).filter((kind) => {
        const item = media[kind];
        if (!isRecord(item)) return false;
        const status = Object.values(ECounselingCaptureStatus).find((value) => item.capture_status === value);
        return status === undefined || captureSafetyState(kind, status) !== "terminal";
      });
    }
    const routine = idOf(data.routine_interview);
    if (routine) {
      resource.paths.add(getRoutineInterviewsGetAssignedQueryKey(routine)[0]);
      resource.paths.add(getRoutineInterviewsGetMineQueryKey(routine)[0]);
      resource.paths.add(getCounselingContextGetOverviewQueryKey("ROUTINE_INTERVIEW", routine)[0]);
    }
    const encounter = idOf(data.counseling_encounter) ?? idOf(data.matching_encounter);
    if (encounter) resource.paths.add(getCounselingGetEncounterQueryKey(encounter)[0]);
    const thread = idOf(data.thread);
    if (thread) resource.paths.add(getGuidanceMessagesGetThreadQueryKey(thread)[0]);
  }

  private unavailableError(id: string) {
    return new CompassApiError({ status: 403, body: { error: { code: "ecounseling_not_found", message: "This E-Counseling session is unavailable." } }, headers: {}, method: "GET", url: getECounselingGetAssignedWorkspaceQueryKey(id)[0] });
  }

  // Local cleanup must retain only this non-sensitive warning, not the denied workspace/media.
  deny(id: string) {
    const resource = this.resource(id);
    if (resource.denial) return;
    const captureKinds = new Set<CaptureKind>(resource.captureKinds);
    for (const key of [getECounselingGetAssignedWorkspaceQueryKey(id), getECounselingGetMyWorkspaceQueryKey(id)]) {
      const media = responseData(this.client.getQueryData(key))?.media;
      if (!isRecord(media)) continue;
      for (const kind of ["recording", "transcription"] as const) {
        const item = media[kind];
        if (!isRecord(item)) continue;
        for (const status of Object.values(ECounselingCaptureStatus)) {
          if (item.capture_status === status && captureSafetyState(kind, status) !== "terminal") captureKinds.add(kind);
        }
      }
    }
    resource.epoch += 1;
    resource.denial = { error: this.unavailableError(id), captureKinds: [...captureKinds] };
    // Emit before asynchronous teardown. Active views also receive an empty error state, so
    // off-route Routine/Encounter/context views cannot continue presenting their cached data.
    this.emit();
    for (const query of this.client.getQueryCache().getAll()) {
      if (this.appointmentFor(query.queryKey) === id) this.conceal(query, resource.denial.error);
    }
  }

  private conceal(query: Query, error: CompassApiError) {
    this.editing = true;
    try {
      void query.cancel({ silent: true, revert: false });
      query.setState({ data: undefined, error, status: "error", fetchStatus: "idle", errorUpdatedAt: Date.now() });
    } finally { this.editing = false; }
  }

  requestFailed(error: unknown) {
    if (!isMutationAuthorityError(error) || !(error instanceof CompassApiError)) return;
    const id = ecounselingAppointment(error.url);
    if (id) this.deny(id);
  }

  mutationStarted(mutation: Mutation<unknown, unknown, unknown>, variables: unknown) {
    const values = isRecord(variables) ? variables : {};
    const key = mutation.options.mutationKey?.[0];
    const metaId = mutation.options.meta?.ecounselingAppointmentId;
    let id = typeof metaId === "string" ? metaId : null;
    if (typeof key === "string") {
      if (key.startsWith("eCounseling") && typeof values.appointmentId === "string") id = values.appointmentId;
      else if (key.startsWith("routineInterviews") && typeof values.routineInterviewId === "string") id = this.appointmentFor(getRoutineInterviewsGetAssignedQueryKey(values.routineInterviewId));
      else if (key.startsWith("counseling") && typeof values.encounterId === "string") id = this.appointmentFor(getCounselingGetEncounterQueryKey(values.encounterId));
      else if (key.startsWith("counseling") && isRecord(values.data) && typeof values.data.appointment_id === "string" && this.resources.has(values.data.appointment_id)) id = values.data.appointment_id;
    }
    if (!id) return;
    this.assertAuthorized(id);
    this.mutations.set(mutation, { id, epoch: this.epoch(id) });
  }
  assertMutationOwner(mutation: Mutation<unknown, unknown, unknown>) {
    const started = this.mutations.get(mutation);
    if (started) this.assertAuthorized(started.id, started.epoch);
  }
}

const accessByClient = new WeakMap<QueryClient, ECounselingResourceAccess>();
export function ecounselingResourceAccess(client: QueryClient): ECounselingResourceAccess {
  let access = accessByClient.get(client);
  if (!access) { access = new ECounselingResourceAccess(client); accessByClient.set(client, access); }
  return access;
}
