// Existing write limits: exit_interviews/services.py and confidential_content.py CONTENT_LIMITS.
// These do not change saved values or the record's current/legacy feedback contract.
export const exitInterviewTextLimits = {
  studentName: 200,
  civilStatus: 80,
  course: 180,
  major: 180,
  emailAddress: 320,
  homeAddress: 2_000,
  contactNumber: 64,
  delayOther: 1_000,
  significantLearningOther: 1_000,
  deanComments: 4_000,
  programChairComments: 4_000,
  facultyComments: 4_000,
  curriculumComments: 4_000,
  guidanceCounselorComments: 4_000,
  officeStaffComments: 4_000,
  facilitiesComments: 4_000,
  suggestionsRecommendations: 4_000,
} as const;
