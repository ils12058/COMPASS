// Short context for a page of results, built only from the canonical page facts: there is no total
// count to report. A single page names how many records it holds; a page among several says which
// page it is.
export function describeResultPage({
  count,
  page,
  hasNext,
  noun,
  filtered = false,
}: {
  count: number;
  page: number;
  hasNext: boolean;
  noun: { one: string; other: string };
  filtered?: boolean;
}): string | null {
  if (count === 0) return null;
  const records = count + " " + (count === 1 ? noun.one : noun.other);
  const scope = filtered ? " matching the filters" : "";
  if (page <= 1 && !hasNext) return records + scope;
  return "Page " + page + " · " + records + scope + " on this page";
}
