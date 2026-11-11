export type GuideStep = { id: string; title: string; description: string; target: HTMLElement; highlight?: boolean };

// Targets belong to the current shell and Home sources. Read only rendered UI; access remains
// owned by the existing role/capability gates, including Faculty availability.
export function orientationSteps(root: HTMLElement): GuideStep[] {
  const target = (name: string) => Array.from(root.querySelectorAll<HTMLElement>(`[data-orientation="${name}"]`))
    .find(element => element.getClientRects().length > 0 && getComputedStyle(element).visibility !== "hidden");
  const steps: GuideStep[] = [];
  const add = (id: string, title: string, description: string, element: HTMLElement | undefined) => {
    if (element) steps.push({ id, title, description, target: element });
  };
  const attention = Array.from(root.querySelectorAll<HTMLElement>("[data-orientation-attention]")).find(element => element.getClientRects().length > 0);
  const shortcuts = Array.from(root.querySelectorAll<HTMLElement>("[data-orientation-shortcuts] a")).find(element => element.getClientRects().length > 0);
  const homeDescription = [
    "Home brings together the information available to you.",
    attention ? `${attention.dataset.orientationAttention} shows items to review and their available next steps.` : "",
    shortcuts ? "The shortcuts on this page open your available destinations." : "",
  ].filter(Boolean).join(" ");
  add("home", "Home", homeDescription, target("home")?.querySelector<HTMLElement>("h1") ?? undefined);
  const desktop = target("desktop-navigation");
  add("navigation", "Portal navigation", desktop
    ? "Choose a destination in the sidebar. Collapse navigation gives you more room; Expand navigation brings back the labels. In the icon rail, labels appear on hover or keyboard focus. Home returns to this page."
    : "Open portal navigation opens the menu drawer. Choose an available destination, or use Close navigation to return to the page. Home returns to this page.", desktop ?? target("mobile-navigation"));
  add("search", "Find a feature", "Go to… searches the COMPASS features you can access. Open it from the portal bar or press Command K or Control K, then choose a destination.", target("search")?.querySelector<HTMLElement>("button") ?? undefined);
  const account = target("account")?.querySelector<HTMLElement>("button") ?? undefined;
  const controls = [
    target("accessibility") ? "Accessibility adjusts text size, spacing, links, and motion." : "",
    target("notifications") ? "Notifications opens your notification list." : "",
    account ? "The user menu opens Account and Sign out." : "",
  ].filter(Boolean).join(" ");
  if (controls) add("controls", "Your portal bar", controls, target("account-controls"));
  add("help", "Help & guides", account
    ? "Open the user menu and choose Help & guides to start or replay Getting around COMPASS. You can also use Guide on Home. Account contains Preferences and your other account settings."
    : "Use Guide on Home to replay Getting around COMPASS whenever you need it.", account ?? target("guide-launch"));
  return steps;
}
