type CapabilityUser = { capabilities: readonly string[] };

// The Services workspace configures the Service Catalog. Catalog reads alone
// are reference data for booking and other workflows and do not open it
// (ADR-059). Every workspace read still requires the catalog read capability.
export function hasServicesWorkspace(user: CapabilityUser): boolean {
  return (
    user.capabilities.includes("services.manage") &&
    user.capabilities.includes("services.catalog.view")
  );
}
