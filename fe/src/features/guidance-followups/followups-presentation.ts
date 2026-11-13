import {
  Category, DueWindow, FollowUpOrdering, StatusValue,
  type FollowUpQuery, type FollowUpSummary,
} from "@/lib/api/generated/model";

export const categoryLabel = (category: Category) => ({
  ADMINISTRATIVE: "Administrative coordination",
  STUDENT_CONTACT: "Student contact",
  COUNSELING: "Counseling Follow-Up",
  REFERRAL_ACTION: "Referral coordination",
}[category]);

export function followupActionLabel(item: Pick<FollowUpSummary, "title" | "category">): string {
  return item.title?.trim() ? item.title : categoryLabel(item.category);
}

export function readFollowupFilters(params: { get: (name: string) => string | null }): FollowUpQuery {
  const status = params.get("status");
  const due = params.get("due_window");
  const ordering = params.get("ordering");
  const page = Number(params.get("page") ?? 1);
  const pageSize = Number(params.get("page_size") ?? 20);
  const uuid = (key: string) => {
    const value = params.get(key);
    return value && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value) ? value : undefined;
  };
  return {
    status: status === "all" ? undefined : Object.values(StatusValue).find(value => value === status) ?? StatusValue.PENDING,
    due_window: Object.values(DueWindow).find(value => value === due),
    ordering: Object.values(FollowUpOrdering).find(value => value === ordering),
    case_id: uuid("case_id"),
    student_id: uuid("student_id"),
    assigned_to_id: uuid("assigned_to_id"),
    page: Number.isInteger(page) && page >= 1 && page <= 100 ? page : 1,
    page_size: Number.isInteger(pageSize) && pageSize >= 1 && pageSize <= 50 ? pageSize : 20,
  };
}
