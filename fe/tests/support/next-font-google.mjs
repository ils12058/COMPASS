// Only the source-owned script font imported by PortalHome is needed in node:test.
export function Caveat({ variable }) {
  return { variable: variable.replace(/^--/, "test-"), className: "test-caveat", style: { fontFamily: "Caveat" } };
}
