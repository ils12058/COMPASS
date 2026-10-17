export type NotificationHeadsUpNotice = {
  key: number;
  count: number;
};

export type NotificationHeadsUpState = {
  baselineEstablished: boolean;
  knownIds: ReadonlySet<string>;
  nextKey: number;
  notice: NotificationHeadsUpNotice | null;
};

export const MAX_KNOWN_NOTIFICATION_IDS = 2_000;

export function createNotificationHeadsUpState(): NotificationHeadsUpState {
  return {
    baselineEstablished: false,
    knownIds: new Set(),
    nextKey: 1,
    notice: null,
  };
}

function boundedIds(ids: Set<string>): Set<string> {
  while (ids.size > MAX_KNOWN_NOTIFICATION_IDS) {
    const oldest = ids.values().next().value;
    if (oldest === undefined) break;
    ids.delete(oldest);
  }
  return ids;
}

export function reconcileNotificationHeadsUp(
  state: NotificationHeadsUpState,
  ids: readonly string[],
  canPresent: boolean,
): NotificationHeadsUpState {
  const knownIds = new Set(state.knownIds);

  if (!state.baselineEstablished) {
    ids.forEach((id) => knownIds.add(id));
    return {
      ...state,
      baselineEstablished: true,
      knownIds: boundedIds(knownIds),
    };
  }

  const newIds: string[] = [];
  for (const id of ids) {
    if (knownIds.has(id)) continue;
    knownIds.add(id);
    newIds.push(id);
  }

  if (!newIds.length) return state;

  const notice = canPresent
    ? state.notice
      ? { ...state.notice, count: state.notice.count + newIds.length }
      : { key: state.nextKey, count: newIds.length }
    : state.notice;

  return {
    ...state,
    knownIds: boundedIds(knownIds),
    nextKey: canPresent && !state.notice ? state.nextKey + 1 : state.nextKey,
    notice,
  };
}

export function dismissNotificationHeadsUp(
  state: NotificationHeadsUpState,
): NotificationHeadsUpState {
  return state.notice ? { ...state, notice: null } : state;
}

export function shouldPresentNotificationHeadsUp(options: {
  muted: boolean;
  activeCall: boolean;
  visible: boolean;
  blockingDialogOpen: boolean;
}): boolean {
  return (
    !options.muted &&
    !options.activeCall &&
    options.visible &&
    !options.blockingDialogOpen
  );
}
