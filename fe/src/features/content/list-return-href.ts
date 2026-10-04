// Detail pages accept only the list's own query keys when linking back to a filtered list.
export function listReturnHref(
  path: string,
  values: URLSearchParams,
  keys: readonly string[],
): string {
  const query = new URLSearchParams();
  for (const key of keys) {
    const value = values.get(key)?.trim();
    if (value) query.set(key, value);
  }
  return query.size ? `${path}?${query.toString()}` : path;
}
