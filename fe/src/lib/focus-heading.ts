// Moves focus to a region's heading when the control that had it no longer exists, such as the
// Remove button of a removed row or the Book button of a review that a stale time took away. The
// heading becomes focusable from script only (tabindex="-1"), so it never joins the Tab order.
export function focusHeading(id: string) {
  const heading = document.getElementById(id);
  if (!heading) return;
  if (!heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
  heading.focus();
}
