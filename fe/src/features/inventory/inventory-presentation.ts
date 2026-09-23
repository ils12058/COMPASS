import {
  AnnualIncomeStatusValue,
  CivilStatusCategoryValue,
  CourseChoiceReasonValue,
  CurrentReligionCategoryValue,
  EducationLevelValue,
  FamilyMemberKindValue,
  FourPsStatusValue,
  HandednessValue,
  IdealAllowanceBandValue,
  ImmunizationValue,
  IndigenousPeoplesStatusValue,
  InterestValue,
  LivingArrangementValue,
  OccupationCategoryValue,
  OrganizationScopeValue,
  ParentLifeStatusValue,
  ParentStatusCategoryValue,
  ParentStatusValue,
  PostGraduationFieldValue,
  PWDStatusValue,
  SexValue,
  TransportationFrequencyCategoryValue,
  TransportationModeValue,
} from "@/lib/api/generated/model";

export const INVENTORY_FORM_CODE = "CNSC-OP-GCO-01F5";

export const inventorySections = [
  { id: "personal", label: "Personal & contact" },
  { id: "family", label: "Family & student support" },
  { id: "background", label: "Siblings & background" },
  { id: "health", label: "Living conditions & health" },
  { id: "education", label: "Educational background" },
  { id: "interests", label: "Interests & daily routine" },
  { id: "organizations", label: "Organizations & transportation" },
  { id: "plans", label: "Plans & counseling context" },
  { id: "review", label: "Review & submit" },
] as const;

export type InventorySectionId = (typeof inventorySections)[number]["id"];

export const sexOptions = [
  [SexValue.MALE, "Male"],
  [SexValue.FEMALE, "Female"],
] as const;

export const civilStatusOptions = [
  [CivilStatusCategoryValue.SINGLE, "Single"],
  [CivilStatusCategoryValue.MARRIED, "Married"],
  [CivilStatusCategoryValue.SOLO_PARENT, "Solo parent"],
  [CivilStatusCategoryValue.OTHER, "Other"],
  [CivilStatusCategoryValue.NOT_SPECIFIED, "Prefer not to specify"],
] as const;

export const religionOptions = [
  [CurrentReligionCategoryValue.ROMAN_CATHOLIC, "Roman Catholic"],
  [CurrentReligionCategoryValue.BORN_AGAIN, "Born Again"],
  [CurrentReligionCategoryValue.IGLESIA_NI_CRISTO, "Iglesia ni Cristo"],
  [CurrentReligionCategoryValue.MORMON, "Mormon"],
  [CurrentReligionCategoryValue.JEHOVAHS_WITNESS, "Jehovah's Witness"],
  [CurrentReligionCategoryValue.SEVENTH_DAY_ADVENTIST, "Seventh-day Adventist"],
  [CurrentReligionCategoryValue.CHURCH_OF_CHRIST, "Church of Christ"],
  [CurrentReligionCategoryValue.EVANGELICAL_CHRISTIAN, "Evangelical Christian"],
  [CurrentReligionCategoryValue.MGCI, "MGCI"],
  [CurrentReligionCategoryValue.BAPTIST, "Baptist"],
  [CurrentReligionCategoryValue.PMCC, "PMCC"],
  [CurrentReligionCategoryValue.NONE, "None"],
  [CurrentReligionCategoryValue.OTHER, "Other"],
  [CurrentReligionCategoryValue.NOT_SPECIFIED, "Prefer not to specify"],
] as const;

export const familyKindOptions = [
  [FamilyMemberKindValue.FATHER, "Father"],
  [FamilyMemberKindValue.MOTHER, "Mother"],
  [FamilyMemberKindValue.SPOUSE, "Spouse"],
] as const;

export const annualIncomeOptions = [
  [AnnualIncomeStatusValue.REPORTED, "Reported"],
  [AnnualIncomeStatusValue.NONE, "None"],
  [AnnualIncomeStatusValue.NOT_SPECIFIED, "Prefer not to specify"],
] as const;

export const occupationOptions = [
  [OccupationCategoryValue.GOVERNMENT_EMPLOYEE, "Government employee"],
  [OccupationCategoryValue.PRIVATE_EMPLOYEE, "Private employee"],
  [OccupationCategoryValue.LABORER, "Laborer"],
  [OccupationCategoryValue.FARMER, "Farmer"],
  [OccupationCategoryValue.SELF_EMPLOYED, "Self-employed"],
  [OccupationCategoryValue.OFW, "Overseas Filipino worker"],
  [OccupationCategoryValue.NONE, "None"],
  [OccupationCategoryValue.OTHER, "Other"],
  [OccupationCategoryValue.NOT_SPECIFIED, "Prefer not to specify"],
] as const;

export const parentStatusCategoryOptions = [
  [ParentStatusCategoryValue.MARRIED, "Married"],
  [ParentStatusCategoryValue.ANNULLED, "Annulled"],
  [ParentStatusCategoryValue.LEGALLY_SEPARATED, "Legally separated"],
  [ParentStatusCategoryValue.TEMPORARILY_SEPARATED, "Temporarily separated"],
  [ParentStatusCategoryValue.PERMANENTLY_SEPARATED, "Permanently separated"],
  [ParentStatusCategoryValue.LIVING_TOGETHER, "Living together"],
  [ParentStatusCategoryValue.WIDOWED, "Widowed"],
  [ParentStatusCategoryValue.MOTHER_WITH_OTHER_PARTNER, "Mother with other partner"],
  [ParentStatusCategoryValue.FATHER_WITH_OTHER_PARTNER, "Father with other partner"],
  [ParentStatusCategoryValue.MOTHER_OFW, "Mother works overseas"],
  [ParentStatusCategoryValue.FATHER_OFW, "Father works overseas"],
  [ParentStatusCategoryValue.OTHER, "Other"],
  [ParentStatusCategoryValue.NOT_SPECIFIED, "Prefer not to specify"],
] as const;

export const parentStatusOptions = [
  [ParentStatusValue.MARRIED_ANNULLED_LEGALLY_SEPARATED, "Married, annulled, or legally separated"],
  [ParentStatusValue.TEMPORARILY_SEPARATED, "Temporarily separated"],
  [ParentStatusValue.PERMANENTLY_SEPARATED, "Permanently separated"],
  [ParentStatusValue.MOTHER_WITH_OTHER_PARTNER, "Mother with another partner"],
  [ParentStatusValue.FATHER_WITH_OTHER_PARTNER, "Father with another partner"],
  [ParentStatusValue.WIDOW_WIDOWER_LIVING_TOGETHER, "Widowed or living together"],
  [ParentStatusValue.MOTHER_OFW, "Mother works overseas"],
  [ParentStatusValue.FATHER_OFW, "Father works overseas"],
] as const;

export const parentLifeOptions = [
  [ParentLifeStatusValue.LIVING, "Alive"],
  [ParentLifeStatusValue.DECEASED, "Deceased"],
  [ParentLifeStatusValue.NOT_SPECIFIED, "Prefer not to specify"],
] as const;

export const fourPsOptions = [
  [FourPsStatusValue.BENEFICIARY, "Yes"],
  [FourPsStatusValue.NOT_BENEFICIARY, "No"],
  [FourPsStatusValue.NOT_SPECIFIED, "Prefer not to specify"],
] as const;

export const indigenousOptions = [
  [IndigenousPeoplesStatusValue.MEMBER, "Yes"],
  [IndigenousPeoplesStatusValue.NOT_MEMBER, "No"],
  [IndigenousPeoplesStatusValue.NOT_SPECIFIED, "Prefer not to specify"],
] as const;

export const livingArrangementOptions = [
  [LivingArrangementValue.OWN_HOUSE, "Own house"],
  [LivingArrangementValue.BOARDING_HOUSE, "Boarding house"],
  [LivingArrangementValue.WITH_RELATIVES, "With relatives"],
] as const;

export const pwdOptions = [
  [PWDStatusValue.PWD, "Person with disability"],
  [PWDStatusValue.NON_PWD, "Not a person with disability"],
  [PWDStatusValue.NOT_SPECIFIED, "Prefer not to specify"],
] as const;

export const educationLevelOptions = [
  [EducationLevelValue.PREPARATORY, "Preparatory"],
  [EducationLevelValue.ELEMENTARY, "Elementary"],
  [EducationLevelValue.JUNIOR_HIGH, "Junior high"],
  [EducationLevelValue.SENIOR_HIGH, "Senior high"],
  [EducationLevelValue.TECHNICAL_VOCATIONAL, "Technical / vocational"],
  [EducationLevelValue.COLLEGIATE, "Collegiate"],
] as const;

export const courseChoiceReasonOptions = [
  [CourseChoiceReasonValue.INTEREST_APTITUDE, "Suited to my interests and aptitude"],
  [CourseChoiceReasonValue.MINIMAL_COST, "Offered at a cost within my family's capacity"],
  [CourseChoiceReasonValue.FRIENDS, "I was invited by friends"],
  [CourseChoiceReasonValue.PARENT_CHOICE, "My parent or guardian's choice"],
  [CourseChoiceReasonValue.JOB_OPPORTUNITIES, "Job opportunities"],
  [CourseChoiceReasonValue.OTHER, "Other reason"],
] as const;

export const interestOptions = [
  [InterestValue.PAINTING, "Painting"],
  [InterestValue.SINGING, "Singing"],
  [InterestValue.POEM_WRITING, "Poem writing"],
  [InterestValue.PLAYING_INSTRUMENTS, "Playing instruments"],
  [InterestValue.PLANTING, "Planting"],
  [InterestValue.DECLAMATION_ORATION, "Declamation or oration"],
  [InterestValue.DANCING, "Dancing"],
  [InterestValue.COMPOSING, "Composing"],
  [InterestValue.STAGE_ACT, "Stage acting"],
  [InterestValue.COOKING, "Cooking"],
] as const;

export const immunizationOptions = [
  [ImmunizationValue.CHICKEN_POX, "Chicken pox"],
  [ImmunizationValue.BOOSTER, "Booster"],
  [ImmunizationValue.MEASLES_MMR, "Measles / MMR"],
  [ImmunizationValue.HEPATITIS_B, "Hepatitis B"],
  [ImmunizationValue.MUMPS, "Mumps"],
  [ImmunizationValue.INFLUENZA, "Influenza"],
  [ImmunizationValue.SMALL_POX, "Smallpox"],
  [ImmunizationValue.OTHER, "Other"],
] as const;

export const handednessOptions = [
  [HandednessValue.RIGHT, "Right"],
  [HandednessValue.LEFT, "Left"],
] as const;

export const allowanceOptions = [
  [IdealAllowanceBandValue.BELOW_100, "Below ₱100"],
  [IdealAllowanceBandValue.FROM_100_TO_499, "₱100–₱499"],
  [IdealAllowanceBandValue.FROM_500_TO_1000, "₱500–₱1,000"],
  [IdealAllowanceBandValue.ABOVE_1000, "Above ₱1,000"],
] as const;

export const workFieldOptions = [
  [PostGraduationFieldValue.PROFESSIONAL, "Professional"],
  [PostGraduationFieldValue.AGRICULTURE, "Agriculture"],
  [PostGraduationFieldValue.BUSINESS, "Business"],
  [PostGraduationFieldValue.TECHNICAL, "Technical"],
  [PostGraduationFieldValue.OVERSEAS_WORKER, "Overseas work"],
  [PostGraduationFieldValue.RELIGIOUS, "Religious service"],
  [PostGraduationFieldValue.PUBLIC_SERVICE, "Public service"],
  [PostGraduationFieldValue.OTHER, "Other"],
] as const;

export const transportationModes = [
  [TransportationModeValue.TRICYCLE, "Tricycle"],
  [TransportationModeValue.BUS, "Bus"],
  [TransportationModeValue.JEEPNEY, "Jeepney"],
  [TransportationModeValue.VAN, "Van"],
  [TransportationModeValue.BOAT, "Boat"],
] as const;

export const transportationFrequencyOptions = [
  [TransportationFrequencyCategoryValue.DAILY, "Daily"],
  [TransportationFrequencyCategoryValue.SEVERAL_TIMES_A_WEEK, "Several times a week"],
  [TransportationFrequencyCategoryValue.WEEKLY, "Weekly"],
  [TransportationFrequencyCategoryValue.OCCASIONAL, "Occasionally"],
  [TransportationFrequencyCategoryValue.OTHER, "Other"],
  [TransportationFrequencyCategoryValue.NOT_SPECIFIED, "Prefer not to specify"],
] as const;

export const organizationScopeOptions = [
  [OrganizationScopeValue.INSIDE_SCHOOL, "Inside the university"],
  [OrganizationScopeValue.OUTSIDE_SCHOOL, "Outside the university"],
] as const;

const enumPresentationLabels: Record<string, string> = Object.fromEntries(
  [
    sexOptions,
    civilStatusOptions,
    religionOptions,
    familyKindOptions,
    annualIncomeOptions,
    occupationOptions,
    parentStatusCategoryOptions,
    parentStatusOptions,
    parentLifeOptions,
    fourPsOptions,
    indigenousOptions,
    livingArrangementOptions,
    pwdOptions,
    educationLevelOptions,
    courseChoiceReasonOptions,
    interestOptions,
    immunizationOptions,
    handednessOptions,
    allowanceOptions,
    workFieldOptions,
    transportationModes,
    transportationFrequencyOptions,
    organizationScopeOptions,
  ].flat(),
);

export function enumLabel(value: string | null | undefined): string {
  if (!value) return "Not provided";
  return enumPresentationLabels[value] ?? value.toLowerCase().replaceAll("_", " ");
}
