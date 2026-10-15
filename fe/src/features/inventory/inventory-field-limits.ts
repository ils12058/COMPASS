import type {
  EducationEntryPayload,
  FamilyMemberPayload,
  InventoryPayload,
  OrganizationMembershipPayload,
  SiblingPayload,
  TransportationEntryPayload,
} from "@/lib/api/generated/model";

// Character limits COMPASS enforces when an Individual Inventory is saved. They mirror the private
// answer limits in be/compass/inventory/confidential_content.py (FIELDS) and the model columns that
// hold the full name and major. Answers the server leaves unbounded, such as addresses and
// narratives, have no entry, so the editor never invents a limit for them.
export const inventoryTextLimits = {
  full_name: 200,
  nickname: 100,
  place_of_birth: 160,
  nationality: 100,
  birth_order_among_siblings: 64,
  civil_status: 80,
  contact_number: 64,
  email_address: 254,
  religion_from_birth: 120,
  current_religion: 120,
  guardian_name: 160,
  guardian_relationship: 120,
  guardian_contact_number: 64,
  emergency_contact_name: 160,
  emergency_contact_number: 64,
  boarding_landlord_name: 160,
  immunization_other: 160,
  height: 64,
  weight: 64,
  major: 180,
  intended_work_other: 160,
  prior_counselor_name: 160,
  prior_counseling_when: 120,
  prior_counseling_where: 200,
} as const satisfies Partial<Record<keyof InventoryPayload, number>>;

export const familyMemberTextLimits = {
  name: 160,
  place_of_birth: 160,
  contact_number: 64,
  email_address: 254,
  educational_attainment: 160,
  occupation: 160,
  business_telephone: 64,
  religion_raised_with: 120,
  current_religion: 120,
} as const satisfies Partial<Record<keyof FamilyMemberPayload, number>>;

export const siblingTextLimits = {
  name: 160,
  educational_attainment: 160,
  occupation: 160,
} as const satisfies Partial<Record<keyof SiblingPayload, number>>;

export const educationTextLimits = {
  inclusive_years: 100,
} as const satisfies Partial<Record<keyof EducationEntryPayload, number>>;

export const organizationTextLimits = {
  organization_name: 180,
  position_title: 160,
} as const satisfies Partial<Record<keyof OrganizationMembershipPayload, number>>;

export const transportationTextLimits = {
  frequency: 100,
} as const satisfies Partial<Record<keyof TransportationEntryPayload, number>>;
