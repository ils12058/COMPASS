from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from compass.api.contract import (
    CURRENT_API_TAGS,
    OPERATION_ID_PATTERN,
    iter_operations,
    validate_openapi_contract,
)
from compass.api.v1.router import api

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPOSITORY_ROOT / "contracts" / "openapi.json"

EXPECTED_OPERATION_IDS = {
    "healthLive",
    "healthReady",
    "platformOperationsHealth",
    "platformOperationsEnvironment",
    "platformOperationsCommandCatalog",
    "platformOperationsGetMaintenance",
    "platformOperationsEnableMaintenance",
    "platformOperationsDisableMaintenance",
    "platformOperationsScheduleMaintenance",
    "platformOperationsCancelMaintenanceSchedule",
    "platformOperationsGetEmailDeliverySummary",
    "platformOperationsListEmailDeliveries",
    "platformOperationsRetryEmailDelivery",
    "platformOperationsListActivity",
    "privacyGovernanceListProcessingActivities",
    "privacyGovernanceGetProcessingActivity",
    "privacyGovernanceCreateProcessingActivity",
    "privacyGovernanceUpdateProcessingActivity",
    "privacyGovernanceRetireProcessingActivity",
    "privacyGovernanceListReviews",
    "privacyGovernanceCreateReview",
    "privacyGovernanceGetReview",
    "privacyGovernanceUpdateReview",
    "privacyGovernanceResolveReview",
    "privacyGovernanceListIncidents",
    "privacyGovernanceCreateIncident",
    "privacyGovernanceGetIncident",
    "privacyGovernanceUpdateIncident",
    "privacyGovernanceResolveIncident",
    "privacyGovernanceListActivity",
    "authGetCsrf",
    "authRequestEmailChangeSecurityChallenge",
    "authRequestEmailChange",
    "authConfirmEmailChange",
    "authLogin",
    "authRequestPasswordAccess",
    "authConfirmPasswordAccess",
    "authVerifyLoginMfa",
    "authLogout",
    "authGetSession",
    "authListSessions",
    "authRevokeOtherSessions",
    "authRevokeSession",
    "authStartTotpSetup",
    "authConfirmTotpSetup",
    "authVerifyTotp",
    "authDisableTotp",
    "authRegenerateRecoveryCodes",
    "authListTrustedSessions",
    "authRevokeOtherTrustedSessions",
    "authRevokeTrustedSession",
    "meListActivity",
    "meListSecurityActivity",
    "profileGetMyProfile",
    "profileUpdateMyProfile",
    "accountsList",
    "accountsCreate",
    "accountsImportCsv",
    "accountsGet",
    "accountsUpdateIdentity",
    "accountsRequestEmailChange",
    "accountsDisable",
    "accountsEnable",
    "accountsChangeRole",
    "accountsUpdateStudentLifecycle",
    "accountsListDesignations",
    "accountsAssignDesignation",
    "accountsRemoveDesignation",
    "accountsListCapabilityOverrides",
    "accountsSetCapabilityOverride",
    "accountsRemoveCapabilityOverride",
    "accountsRevokeSessions",
    "accountsRevokeTrustedSessions",
    "accountsResetMfa",
    "organizationListCampuses",
    "organizationCreateCampus",
    "organizationGetCampus",
    "organizationUpdateCampus",
    "organizationEnableCampus",
    "organizationDisableCampus",
    "organizationListColleges",
    "organizationCreateCollege",
    "organizationGetCollege",
    "organizationUpdateCollege",
    "organizationEnableCollege",
    "organizationDisableCollege",
    "organizationListPrograms",
    "organizationCreateProgram",
    "organizationGetProgram",
    "organizationUpdateProgram",
    "organizationEnableProgram",
    "organizationDisableProgram",
    "organizationListCounselorResponsibilities",
    "organizationSetCollegeCounselor",
    "organizationRemoveCollegeCounselor",
    "organizationListStaffSupervisions",
    "organizationSetStaffSupervisor",
    "organizationRemoveStaffSupervisor",
    "organizationListStudentAffiliations",
    "organizationSetStudentAffiliation",
    "organizationRemoveStudentAffiliation",
    "organizationListEligiblePeople",
    "servicesList",
    "servicesCreate",
    "servicesGet",
    "servicesUpdate",
    "servicesEnable",
    "servicesDisable",
    "availabilityGetOfficeWeekly",
    "availabilityReplaceOfficeWeekly",
    "availabilityListOfficeExceptions",
    "availabilityCreateOfficeException",
    "availabilityRemoveOfficeException",
    "availabilityGetMyWeekly",
    "availabilityReplaceMyWeekly",
    "availabilityListMyExceptions",
    "availabilityCreateMyException",
    "availabilityRemoveMyException",
    "availabilityGetProviderWeekly",
    "availabilityReplaceProviderWeekly",
    "availabilityListProviderExceptions",
    "availabilityCreateProviderException",
    "availabilityRemoveProviderException",
    "availabilityGetProviderEffective",
    "appointmentsCreateMy",
    "appointmentsListMy",
    "appointmentsListManaged",
    "appointmentsGet",
    "appointmentsCancel",
    "appointmentsListEligibleCounselors",
    "counselingCreateEncounter",
    "counselingListMyEncounters",
    "counselingGetEncounter",
    "counselingUpdateEncounter",
    "counselingListStudents",
    "counselingGetAssignedSharedSummary",
    "counselingPutAssignedSharedSummary",
    "counselingPublishAssignedSharedSummary",
    "counselingListMySharedSummaries",
    "counselingGetMySharedSummary",
    "academicYearsList",
    "academicYearsCreate",
    "academicYearsSetCurrent",
    "institutionalFormsList",
    "institutionalFormsRevisionsList",
    "institutionalFormsRevisionsRegister",
    "institutionalFormsRevisionsActivate",
    "institutionalFormsRevisionsDeactivate",
    "inventoryGetMyStatus",
    "inventoryGetMyCurrent",
    "inventoryEnsureMyCurrent",
    "inventoryUpdateMyCurrent",
    "inventorySubmitMyCurrent",
    "inventoryListMyHistory",
    "inventoryGetMyHistoryItem",
    "studentSupportGetContext",
    "reportsGetStudentProfile",
    "reportsDownloadStudentProfilePdf",
    "reportsDownloadStudentProfileXlsx",
    "reportsGetGraduateTracer",
    "reportsDownloadGraduateTracerXlsx",
    "goodMoralCreateMyCurrentStudentRequest",
    "goodMoralCreateMyGraduateRequest",
    "goodMoralListMyRequests",
    "goodMoralGetMyRequest",
    "goodMoralDownloadMyCertificate",
    "goodMoralListRequests",
    "goodMoralGetRequest",
    "goodMoralUpdateRequest",
    "goodMoralIssueRequest",
    "goodMoralDownloadCertificate",
    "feedbackSubmitCustomerFeedback",
    "feedbackListCustomerFeedbackResponses",
    "feedbackGetCustomerFeedbackResponse",
    "feedbackSubmitCsm",
    "feedbackListCsmResponses",
    "feedbackGetCsmResponse",
    "graduateTracerEnsureMyResponse",
    "graduateTracerGetMyResponse",
    "graduateTracerReplaceMyDraft",
    "graduateTracerSubmitMyResponse",
    "graduateTracerListResponses",
    "graduateTracerGetResponse",
    "exitInterviewsEnsureMyCurrent",
    "exitInterviewsGetMyCurrent",
    "exitInterviewsUpdateMyCurrent",
    "exitInterviewsSubmitMyCurrent",
    "exitInterviewsListMine",
    "exitInterviewsGetMine",
    "exitInterviewsList",
    "exitInterviewsGet",
    "exitInterviewsReopen",
    "routineInterviewsEnsureMyForAppointment",
    "routineInterviewsCreateDirect",
    "routineInterviewsListMine",
    "routineInterviewsGetMine",
    "routineInterviewsReplaceMyIntake",
    "routineInterviewsSubmitMyIntake",
    "routineInterviewsGetAssigned",
    "routineInterviewsReplaceAssignedEvaluation",
    "routineInterviewsFinalizeAssignedEvaluation",
    "referralsCreate",
    "referralsList",
    "referralsGet",
    "referralsUpdateStatus",
    "referralsRecordAction",
    "callSlipsCreate",
    "callSlipsList",
    "callSlipsGet",
    "callSlipsListMy",
    "callSlipsGetMy",
    "callSlipsRecordInterviewEnded",
    "notificationsListMine",
    "notificationsGetUnreadCount",
    "notificationsMarkRead",
    "notificationsGetPreferences",
    "notificationsUpdatePreferences",
    "documentBrandingGetProfile",
    "documentBrandingUpdateProfile",
    "eCounselingGetMyWorkspace",
    "eCounselingGetAssignedWorkspace",
    "eCounselingListMyConsents",
    "eCounselingListAssignedConsents",
    "eCounselingRequestConsent",
    "eCounselingDecideMyConsent",
    "eCounselingWithdrawMyConsent",
    "eCounselingStartAssignedRecording",
    "eCounselingStopAssignedRecording",
    "eCounselingStartAssignedTranscription",
    "eCounselingStopAssignedTranscription",
    "eCounselingCreateJoinCredential",
    "eCounselingDailyWebhook",
}


def _generated_schema() -> dict:
    schema = dict(api.get_openapi_schema())
    validate_openapi_contract(schema)
    return json.loads(json.dumps(schema))


def _operation(schema: dict, path: str, method: str) -> dict:
    return schema["paths"][path][method]


def _response_statuses(operation: dict) -> set[int]:
    return {int(status) for status in operation["responses"]}


def test_generated_schema_matches_committed_contract() -> None:
    assert CONTRACT_PATH.is_file()
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert committed == _generated_schema()


def test_contract_command_exports_and_checks_normalized_schema(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"
    call_command("export_openapi", output=output)
    call_command("export_openapi", output=output, check=True)

    output.write_text(json.dumps({"stale": True}), encoding="utf-8")
    with pytest.raises(CommandError, match="OpenAPI contract is stale"):
        call_command("export_openapi", output=output, check=True)


def test_all_public_operations_have_stable_unique_ids_and_approved_tags() -> None:
    schema = _generated_schema()
    operations = list(iter_operations(schema))
    operation_ids = [operation["operationId"] for _, _, operation in operations]

    route_operations = [
        operation
        for bound_router in api._get_bound_routers()
        for path_view in bound_router.path_operations.values()
        for operation in path_view.operations
        if operation.include_in_schema
    ]
    assert route_operations
    assert all(operation.operation_id for operation in route_operations)

    assert len(operation_ids) == len(EXPECTED_OPERATION_IDS)
    assert set(operation_ids) == EXPECTED_OPERATION_IDS
    assert len(operation_ids) == len(set(operation_ids))
    assert all(OPERATION_ID_PATTERN.fullmatch(operation_id) for operation_id in operation_ids)
    assert all("compass" not in operation_id.lower() for operation_id in operation_ids)
    assert [tag["name"] for tag in schema["tags"]] == [
        "health",
        "auth",
        "activity",
        "profile",
        "accounts",
        "organization",
        "services",
        "availability",
        "appointments",
        "counseling",
        "academic-years",
        "institutional-forms",
        "inventory",
        "student-support",
        "reports",
        "good-moral",
        "feedback",
        "graduate-tracer",
        "exit-interviews",
        "routine-interviews",
        "referrals",
        "call-slips",
        "notifications",
        "document-branding",
        "e-counseling",
        "platform-operations",
        "privacy-governance",
    ]
    assert all(
        isinstance(operation.get("tags"), list)
        and len(operation["tags"]) == 1
        and operation["tags"][0] in CURRENT_API_TAGS
        for _, _, operation in operations
    )


def test_cookie_auth_and_public_csrf_contract_are_explicit() -> None:
    schema = _generated_schema()
    security_scheme = schema["components"]["securitySchemes"]["OpaqueSessionAuth"]
    assert security_scheme["type"] == "apiKey"
    assert security_scheme["in"] == "cookie"
    assert security_scheme["name"] == "compass_session"
    assert "HttpOnly" in security_scheme["description"]
    assert "Bearer" in security_scheme["description"]
    assert not any(
        value.get("type") == "http" for value in schema["components"]["securitySchemes"].values()
    )

    csrf = _operation(schema, "/api/v1/auth/csrf", "get")
    assert "security" not in csrf
    assert csrf["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/CSRFResponse"
    )
    assert "CSRF" in csrf["description"]

    health_live = _operation(schema, "/api/v1/health/live", "get")
    assert "security" not in health_live
    daily_webhook = _operation(schema, "/api/v1/integrations/daily/webhook", "post")
    assert "security" not in daily_webhook

    secured_operations = [
        operation for _, _, operation in iter_operations(schema) if "security" in operation
    ]
    assert secured_operations
    assert all(
        operation["security"] == [{"OpaqueSessionAuth": []}] for operation in secured_operations
    )


def test_core_schemas_and_realistic_error_responses_are_typed() -> None:
    schema = _generated_schema()
    schemas = schema["components"]["schemas"]
    expected_schemas = {
        "APIErrorDetail",
        "APIErrorResponse",
        "ValidationIssue",
        "AccountCreateRequest",
        "AccountDetailResponse",
        "AccountListResponse",
        "EmailChangeSecurityChallengeRequest",
        "EmailChangeSecurityChallengeResponse",
        "EmailChangeRequest",
        "EmailChangeRequestResponse",
        "EmailChangeConfirmRequest",
        "EmailChangeConfirmResponse",
        "ManagedEmailChangeRequest",
        "ManagedEmailChangeResponse",
        "ActivityPageResponse",
        "MyProfileResponse",
        "MyProfileUpdateRequest",
        "PasswordAccessRequest",
        "PasswordAccessRequestResponse",
        "PasswordAccessConfirmRequest",
        "PasswordAccessConfirmResponse",
        "LoginRequest",
        "LoginResponse",
        "SessionListResponse",
        "CounselingEncounterResponse",
        "CounselingStudentPageResponse",
        "CounselingAssignedSharedSummaryResponse",
        "CounselingStudentSharedSummaryPageResponse",
        "StudentWorkspaceResponse",
        "CounselorWorkspaceResponse",
        "MediaWorkspaceState",
        "ConsentResponse",
        "ConsentListResponse",
        "MediaCaptureResponse",
        "JoinCredentialResponse",
        "WebhookAckResponse",
        "DocumentBrandingProfileResponse",
        "ExitInterviewDraftPayload",
        "ExitInterviewDetailResponse",
        "ExitInterviewSummaryResponse",
        "ExitInterviewPageResponse",
        "SelfAssessmentRatingPayload",
        "CollegeFeedbackRatingPayload",
        "ReopenRequest",
        "GraduateTracerDraftPayload",
        "GraduateTracerDetailResponse",
        "GraduateTracerSummaryResponse",
        "GraduateTracerPageResponse",
        "GraduateTracerEducationPayload",
        "GraduateTracerProfessionalExamPayload",
        "GraduateTracerTrainingPayload",
        "ProgramSummary",
        "ProgramListResponse",
        "ProgramCreateRequest",
        "ProgramUpdateRequest",
        "InventoryProgramSummary",
        "CivilStatusCategoryValue",
        "CurrentReligionCategoryValue",
        "PWDStatusValue",
        "FourPsStatusValue",
        "IndigenousPeoplesStatusValue",
        "ParentLifeStatusValue",
        "SupportProfilePayload",
        "StudentSupportContextResponse",
        "SupportIndicatorResponse",
        "StudentReference",
        "AcademicYearReference",
        "ParentStatusCategoryValue",
        "OccupationCategoryValue",
        "AnnualIncomeStatusValue",
        "GeographicLocationKindValue",
        "TransportationFrequencyCategoryValue",
        "GeographicLocationPayload",
        "StudentProfilingReportResponse",
        "ReportContext",
        "ProgramColumn",
        "InventoryCoverage",
        "Methodology",
        "StudentProfilingSections",
        "DistributionSection",
        "DistributionRow",
        "ProgramCount",
        "GeographicDistributionSection",
        "GeographicDistributionRow",
    }
    assert expected_schemas <= schemas.keys()
    assert schemas["AccountSummaryResponse"]["properties"]["id"]["format"] == "uuid"
    assert schemas["AccountSummaryResponse"]["properties"]["created_at"]["format"] == "date-time"
    account_summary = schemas["AccountSummaryResponse"]["properties"]
    account_detail = schemas["AccountDetailResponse"]["properties"]
    assert "student_lifecycle_status" in account_summary
    assert "password_configured" in account_summary
    assert "email_verified" in account_summary
    assert "email_verified_at" not in account_summary
    assert "email_verified_at" in account_detail
    assert "student_lifecycle_status" in schemas["UserSummary"]["properties"]
    assert "INSTITUTIONAL_OFFICER" in schemas["RoleCode"]["enum"]
    assert (
        _operation(
            schema,
            "/api/v1/accounts/{user_id}/student-lifecycle",
            "put",
        )["operationId"]
        == "accountsUpdateStudentLifecycle"
    )
    assert schemas["AccountListResponse"]["properties"]["items"]["type"] == "array"
    assert schemas["APIErrorResponse"]["properties"]["error"]["$ref"].endswith("/APIErrorDetail")
    assert schemas["APIErrorDetail"]["properties"]["details"]["anyOf"]
    assert _operation(schema, "/api/v1/accounts", "post")["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/AccountCreateRequest")
    csv_import_operation = _operation(schema, "/api/v1/accounts/imports/csv", "post")
    assert csv_import_operation["operationId"] == "accountsImportCsv"
    assert "multipart/form-data" in csv_import_operation["requestBody"]["content"]
    assert _operation(
        schema,
        "/api/v1/auth/email-change/security-challenge",
        "post",
    )["operationId"] == "authRequestEmailChangeSecurityChallenge"
    assert _operation(
        schema,
        "/api/v1/auth/email-change/request",
        "post",
    )["operationId"] == "authRequestEmailChange"
    assert _operation(
        schema,
        "/api/v1/auth/email-change/confirm",
        "post",
    )["operationId"] == "authConfirmEmailChange"
    assert _operation(
        schema,
        "/api/v1/accounts/{user_id}/email-change",
        "post",
    )["operationId"] == "accountsRequestEmailChange"
    assert _operation(schema, "/api/v1/auth/login", "post")["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/LoginRequest")
    assert _operation(schema, "/api/v1/auth/password/request", "post")["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/PasswordAccessRequest")
    assert _operation(schema, "/api/v1/auth/password/confirm", "post")["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/PasswordAccessConfirmRequest")
    profile_response = schemas["MyProfileResponse"]["properties"]
    assert {
        "user_id",
        "institutional_id",
        "email",
        "first_name",
        "middle_name",
        "last_name",
        "suffix",
        "full_name",
        "role",
        "date_of_birth",
        "civil_status",
        "contact_number",
        "current_address",
        "permanent_address",
        "profile_photo_url",
        "profile_photo_updated_at",
    } <= set(profile_response)
    assert "profile_photo_object_key" not in profile_response
    profile_update = schemas["MyProfileUpdateRequest"]["properties"]
    assert set(profile_update) == {
        "date_of_birth",
        "civil_status",
        "contact_number",
        "current_address",
        "permanent_address",
    }
    assert "email" not in profile_update
    assert "first_name" not in profile_update
    assert "role" not in profile_update
    assert "profile_photo_object_key" not in profile_update

    program_summary = schemas["ProgramSummary"]["properties"]
    assert {"id", "code", "name", "college", "is_active"} == set(program_summary)
    program_create = schemas["ProgramCreateRequest"]["properties"]
    assert {"college_id", "code", "name"} == set(program_create)
    program_update = schemas["ProgramUpdateRequest"]["properties"]
    assert {"code", "name"} == set(program_update)

    inventory_payload = schemas["InventoryPayload"]["properties"]
    assert {
        "program_id",
        "year_level",
        "course_currently_enrolled",
        "major",
        "civil_status_category",
        "current_religion_category",
        "pwd_status",
        "parent_status_category",
        "support_profile",
        "geographic_locations",
    } <= set(inventory_payload)
    assert inventory_payload["program_id"]["anyOf"][0]["format"] == "uuid"
    assert inventory_payload["year_level"]["anyOf"][0]["minimum"] == 1
    assert inventory_payload["year_level"]["anyOf"][0]["maximum"] == 10
    inventory_response = schemas["InventoryResponse"]["properties"]
    assert "program" in inventory_response
    assert inventory_response["program"]["anyOf"][0]["$ref"].endswith("/InventoryProgramSummary")
    family_member = schemas["FamilyMemberPayload"]["properties"]
    assert {"occupation_category", "annual_income_status"} <= set(family_member)
    assert "life_status" not in family_member
    assert "physical_disadvantage_status" not in inventory_payload
    support_profile = schemas["SupportProfilePayload"]["properties"]
    assert set(support_profile) == {
        "four_ps_status",
        "indigenous_peoples_status",
        "mother_life_status",
        "father_life_status",
    }
    transport = schemas["TransportationEntryPayload"]["properties"]
    assert "frequency_category" in transport
    location = schemas["GeographicLocationPayload"]["properties"]
    assert {
        "kind",
        "not_specified",
        "region_psgc_code",
        "region_name_snapshot",
        "province_psgc_code",
        "province_name_snapshot",
        "city_municipality_psgc_code",
        "city_municipality_name_snapshot",
        "barangay_psgc_code",
        "barangay_name_snapshot",
    } == set(location)

    support_context = schemas["StudentSupportContextResponse"]["properties"]
    assert set(support_context) == {
        "student",
        "academic_year",
        "inventory_status",
        "available",
        "indicators",
    }
    support_operation = _operation(
        schema,
        "/api/v1/student-support/students/{student_id}/context",
        "get",
    )
    assert support_operation["operationId"] == "studentSupportGetContext"
    assert support_operation["tags"] == ["student-support"]

    exit_draft = schemas["ExitInterviewDraftPayload"]["properties"]
    assert {
        "student_name",
        "age",
        "civil_status",
        "course",
        "major",
        "email_address",
        "home_address",
        "contact_number",
        "program_completion",
        "extra_terms_count",
        "delay_reasons",
        "delay_other",
        "significant_learning_experiences",
        "significant_learning_other",
        "career_modes",
        "work_choices",
        "study_choices",
        "self_assessment_ratings",
        "college_feedback_ratings",
        "dean_comments",
        "program_chair_comments",
        "faculty_comments",
        "curriculum_comments",
        "guidance_counselor_comments",
        "office_staff_comments",
        "facilities_comments",
        "suggestions_recommendations",
    } == set(exit_draft)
    assert {
        "student_id",
        "academic_year_id",
        "inventory_id",
        "form_revision_id",
        "status",
        "created_at",
        "first_submitted_at",
        "last_submitted_at",
        "reopened_by",
    }.isdisjoint(exit_draft)

    graduate_tracer_draft = schemas["GraduateTracerDraftPayload"]["properties"]
    assert {
        "name",
        "permanent_address",
        "email",
        "telephone_contact_numbers",
        "mobile_number",
        "civil_status",
        "sex",
        "birth_date",
        "region_of_origin",
        "province",
        "residence_location",
        "education",
        "professional_exams",
        "undergraduate_degree_reasons",
        "graduate_study_reasons",
        "degree_other_reason",
        "trainings",
        "advanced_study_reasons",
        "advanced_study_other_reason",
        "current_employment_state",
        "unemployment_reasons",
        "unemployment_other_reason",
        "present_employment_status",
        "present_occupation",
        "employer_business_line",
        "place_of_work",
        "first_job_after_college",
        "time_to_first_job",
        "curriculum_improvement_suggestions",
    } <= set(graduate_tracer_draft)
    student_profile = schemas["StudentProfilingReportResponse"]["properties"]
    assert set(student_profile) == {
        "report_context",
        "methodology",
        "program_columns",
        "inventory_coverage",
        "sections",
    }
    report_context = schemas["ReportContext"]["properties"]
    assert {
        "academic_year",
        "campus",
        "college",
        "program",
        "year_level",
        "year_level_label",
        "submitted_inventory_count",
        "generated_at",
    } == set(report_context)
    assert schemas["PWDStatusValue"]["enum"] == ["PWD", "NON_PWD", "NOT_SPECIFIED"]
    assert schemas["FourPsStatusValue"]["enum"] == [
        "BENEFICIARY",
        "NOT_BENEFICIARY",
        "NOT_SPECIFIED",
    ]
    assert schemas["IndigenousPeoplesStatusValue"]["enum"] == [
        "MEMBER",
        "NOT_MEMBER",
        "NOT_SPECIFIED",
    ]
    assert schemas["DistributionRow"]["properties"]["percentage"]["type"] == "number"
    assert schemas["InventoryCoverage"]["properties"]["missing_count"]["anyOf"][-1] == {
        "type": "null"
    }
    assert _operation(schema, "/api/v1/reports/student-profile", "get")["operationId"] == (
        "reportsGetStudentProfile"
    )
    graduate_report = schemas["GraduateTracerReportResponse"]["properties"]
    assert set(graduate_report) == {"report_context", "methodology", "sections"}
    graduate_context = schemas["GraduateTracerReportContext"]["properties"]
    assert set(graduate_context) == {
        "instrument_schema_version",
        "submitted_from",
        "submitted_to",
        "submitted_response_count",
        "generated_at",
    }
    assert schemas["GraduateTracerDistributionRow"]["properties"]["percentage"]["type"] == "number"
    graduate_operation = _operation(schema, "/api/v1/reports/graduate-tracer", "get")
    assert graduate_operation["operationId"] == "reportsGetGraduateTracer"
    assert graduate_operation["tags"] == ["reports"]
    graduate_xlsx = _operation(schema, "/api/v1/reports/graduate-tracer/xlsx", "get")
    assert graduate_xlsx["operationId"] == "reportsDownloadGraduateTracerXlsx"
    assert graduate_xlsx["tags"] == ["reports"]

    assert {
        "student_id",
        "instrument_schema_version",
        "status",
        "submitted_at",
        "created_at",
        "updated_at",
    }.isdisjoint(graduate_tracer_draft)
    assert schemas["SelfAssessmentRatingPayload"]["properties"]["rating"]["minimum"] == 1
    assert schemas["SelfAssessmentRatingPayload"]["properties"]["rating"]["maximum"] == 5
    assert schemas["CollegeFeedbackRatingPayload"]["properties"]["rating"]["minimum"] == 0
    assert schemas["CollegeFeedbackRatingPayload"]["properties"]["rating"]["maximum"] == 5
    assert len(schemas["SelfAssessmentItemValue"]["enum"]) == 15
    assert len(schemas["CollegeFeedbackItemValue"]["enum"]) == 26

    assert "password" not in schemas["AccountCreateRequest"]["properties"]
    assert {"institutional_id", "email", "first_name", "last_name", "role"} <= set(
        schemas["AccountCreateRequest"]["required"]
    )
    assert "institutional_id" in schemas["AccountSummaryResponse"]["properties"]
    assert "email" not in schemas["IdentityUpdateRequest"]["properties"]
    assert "institutional_id" in schemas["IdentityUpdateRequest"]["properties"]
    assert schemas["LoginResponse"]["properties"]["session_id"]["anyOf"][-1] == {"type": "null"}

    assert _response_statuses(_operation(schema, "/api/v1/auth/login", "post")) >= {
        200,
        401,
        403,
        422,
        429,
        503,
    }
    assert _response_statuses(_operation(schema, "/api/v1/auth/password/request", "post")) >= {
        202,
        400,
        403,
        422,
        429,
        503,
    }
    assert _response_statuses(_operation(schema, "/api/v1/auth/password/confirm", "post")) >= {
        200,
        400,
        403,
        422,
        429,
        503,
    }
    assert _response_statuses(_operation(schema, "/api/v1/me/profile", "get")) >= {
        200,
        401,
        403,
    }
    assert _response_statuses(_operation(schema, "/api/v1/me/profile", "patch")) >= {
        200,
        401,
        403,
        422,
    }

    assert _response_statuses(_operation(schema, "/api/v1/organization/programs", "get")) >= {
        200,
        401,
        403,
        422,
    }
    assert _response_statuses(_operation(schema, "/api/v1/organization/programs", "post")) >= {
        201,
        401,
        403,
        404,
        409,
        422,
    }
    assert _response_statuses(
        _operation(schema, "/api/v1/organization/programs/{program_id}", "get")
    ) >= {200, 401, 403, 404, 422}
    assert _response_statuses(
        _operation(schema, "/api/v1/organization/programs/{program_id}", "patch")
    ) >= {200, 401, 403, 404, 409, 422}
    assert _response_statuses(
        _operation(schema, "/api/v1/organization/programs/{program_id}/enable", "post")
    ) >= {200, 401, 403, 404, 409, 422}
    assert _response_statuses(
        _operation(schema, "/api/v1/organization/programs/{program_id}/disable", "post")
    ) >= {200, 401, 403, 404, 409, 422}

    assert _response_statuses(
        _operation(
            schema,
            "/api/v1/student-support/students/{student_id}/context",
            "get",
        )
    ) >= {200, 401, 403, 404, 409}

    assert _response_statuses(_operation(schema, "/api/v1/reports/student-profile", "get")) >= {
        200,
        401,
        403,
        404,
        409,
        422,
    }

    assert _response_statuses(
        _operation(schema, "/api/v1/reports/student-profile/xlsx", "get")
    ) >= {
        200,
        401,
        403,
        404,
        409,
        422,
        503,
    }
    assert _response_statuses(_operation(schema, "/api/v1/reports/graduate-tracer", "get")) >= {
        200,
        401,
        403,
        422,
    }
    assert _response_statuses(
        _operation(schema, "/api/v1/reports/graduate-tracer/xlsx", "get")
    ) >= {
        200,
        401,
        403,
        422,
        503,
    }

    assert _response_statuses(_operation(schema, "/api/v1/graduate-tracer/me", "post")) >= {
        200,
        401,
        403,
        409,
        422,
    }
    assert _response_statuses(_operation(schema, "/api/v1/graduate-tracer/me", "get")) >= {
        200,
        401,
        403,
        404,
    }
    assert _response_statuses(_operation(schema, "/api/v1/graduate-tracer/me", "put")) >= {
        200,
        401,
        403,
        404,
        409,
        422,
    }
    assert _response_statuses(_operation(schema, "/api/v1/graduate-tracer/me/submit", "post")) >= {
        200,
        401,
        403,
        404,
        409,
        422,
    }
    assert _response_statuses(_operation(schema, "/api/v1/graduate-tracer/responses", "get")) >= {
        200,
        401,
        403,
        422,
    }
    assert _response_statuses(
        _operation(schema, "/api/v1/graduate-tracer/responses/{response_id}", "get")
    ) >= {200, 401, 403, 404, 422}

    assert _response_statuses(_operation(schema, "/api/v1/exit-interviews/me/current", "post")) >= {
        200,
        401,
        403,
        409,
        422,
    }
    assert _response_statuses(_operation(schema, "/api/v1/exit-interviews/me/current", "get")) >= {
        200,
        401,
        403,
        404,
        409,
    }
    assert _response_statuses(_operation(schema, "/api/v1/exit-interviews/me/current", "put")) >= {
        200,
        401,
        403,
        404,
        409,
        422,
    }
    assert _response_statuses(
        _operation(schema, "/api/v1/exit-interviews/me/current/submit", "post")
    ) >= {200, 401, 403, 404, 409, 422}
    assert _response_statuses(_operation(schema, "/api/v1/exit-interviews/me", "get")) >= {
        200,
        401,
        403,
    }
    assert _response_statuses(_operation(schema, "/api/v1/exit-interviews", "get")) >= {
        200,
        401,
        403,
        422,
    }
    assert _response_statuses(
        _operation(schema, "/api/v1/exit-interviews/{exit_interview_id}/reopen", "post")
    ) >= {200, 401, 403, 404, 409, 422}
    assert _response_statuses(_operation(schema, "/api/v1/accounts", "post")) >= {
        201,
        401,
        403,
        409,
        422,
        503,
    }
    assert _response_statuses(_operation(schema, "/api/v1/accounts/imports/csv", "post")) >= {
        200,
        401,
        403,
        409,
        422,
        503,
    }
    assert _response_statuses(_operation(schema, "/api/v1/accounts/{user_id}", "get")) >= {
        200,
        401,
        403,
        404,
        422,
    }
    assert _response_statuses(_operation(schema, "/api/v1/health/ready", "get")) == {200, 503}
    assert _response_statuses(
        _operation(schema, "/api/v1/availability/providers/{provider_id}/effective", "get")
    ) >= {200, 401, 403, 404, 409, 422}
    assert _response_statuses(_operation(schema, "/api/v1/appointments", "post")) >= {
        201,
        401,
        403,
        409,
        422,
        503,
    }
    assert _response_statuses(
        _operation(schema, "/api/v1/appointments/{appointment_id}/cancel", "post")
    ) >= {200, 401, 403, 404, 409, 422}
    assert _response_statuses(_operation(schema, "/api/v1/counseling/encounters", "post")) >= {
        201,
        401,
        403,
        409,
        422,
    }
    assert _response_statuses(
        _operation(schema, "/api/v1/counseling/encounters/{encounter_id}", "patch")
    ) >= {200, 401, 403, 404, 409, 422}
    assert _response_statuses(
        _operation(schema, "/api/v1/counseling/encounters/{encounter_id}/shared-summary", "put")
    ) >= {200, 401, 403, 404, 409, 422}
    assert _response_statuses(
        _operation(
            schema,
            "/api/v1/counseling/encounters/{encounter_id}/shared-summary/publish",
            "post",
        )
    ) >= {200, 401, 403, 404, 409, 422}
    assert _response_statuses(
        _operation(schema, "/api/v1/e-counseling/appointments/{appointment_id}/join", "post")
    ) >= {200, 401, 403, 404, 409, 502, 503}
    assert _response_statuses(
        _operation(schema, "/api/v1/e-counseling/appointments/{appointment_id}/consents", "post")
    ) >= {200, 401, 403, 404, 409, 422}
    assert _response_statuses(
        _operation(
            schema, "/api/v1/e-counseling/appointments/{appointment_id}/recording/start", "post"
        )
    ) >= {200, 401, 403, 404, 409, 502, 503}
    assert _response_statuses(
        _operation(
            schema,
            "/api/v1/e-counseling/appointments/{appointment_id}/transcription/start",
            "post",
        )
    ) >= {200, 401, 403, 404, 409, 422, 502, 503}
    assert _response_statuses(_operation(schema, "/api/v1/integrations/daily/webhook", "post")) >= {
        200,
        400,
        403,
        503,
    }

    assert _response_statuses(_operation(schema, "/api/v1/call-slips", "post")) >= {
        201,
        401,
        403,
        404,
        409,
        422,
    }
    assert _response_statuses(_operation(schema, "/api/v1/call-slips", "get")) >= {
        200,
        401,
        403,
        422,
    }
    assert _response_statuses(_operation(schema, "/api/v1/call-slips/me", "get")) >= {
        200,
        401,
        403,
        422,
    }
    assert _response_statuses(
        _operation(schema, "/api/v1/call-slips/{call_slip_id}/interview-ended", "patch")
    ) >= {200, 401, 403, 404, 409, 422}

    assert _response_statuses(_operation(schema, "/api/v1/notifications", "get")) >= {
        200,
        401,
        422,
    }
    assert _response_statuses(_operation(schema, "/api/v1/notifications/unread-count", "get")) >= {
        200,
        401,
    }
    assert _response_statuses(
        _operation(schema, "/api/v1/notifications/{notification_id}/read", "patch")
    ) >= {200, 401, 404}
    assert _response_statuses(_operation(schema, "/api/v1/notifications/preferences", "get")) >= {
        200,
        401,
    }
    assert _response_statuses(_operation(schema, "/api/v1/notifications/preferences", "patch")) >= {
        200,
        401,
    }
    assert _response_statuses(_operation(schema, "/api/v1/document-branding/profile", "get")) >= {
        200,
        401,
        403,
        503,
    }
    assert _response_statuses(_operation(schema, "/api/v1/document-branding/profile", "patch")) >= {
        200,
        401,
        403,
        422,
        503,
    }

    for method, path, operation in iter_operations(schema):
        for status, response in operation["responses"].items():
            if int(status) in {400, 401, 403, 404, 409, 422, 429, 502, 503}:
                if method == "get" and path == "/api/v1/health/ready" and int(status) == 503:
                    continue
                response_schema = response["content"]["application/json"]["schema"]
                assert response_schema["$ref"].endswith("/APIErrorResponse")


def test_policy_enums_and_sensitive_model_fields_are_contract_safe() -> None:
    schema = _generated_schema()
    schemas = schema["components"]["schemas"]
    assert schemas["RoleCode"]["enum"] == [
        "COUNSELOR",
        "GUIDANCE_SERVICES_STAFF",
        "INSTITUTIONAL_OFFICER",
        "IT_ADMIN",
        "STUDENT",
    ]
    assert schemas["DesignationCode"]["enum"] == ["DPO", "HEAD_GUIDANCE_COUNSELOR"]
    assert schemas["CapabilityCode"]["enum"] == sorted(
        [
            "accounts.manage",
            "accounts.view",
            "academic_years.manage",
            "academic_years.view",
            "appointments.manage",
            "appointments.manage_self",
            "appointments.view_self",
            "availability.manage",
            "availability.manage_self",
            "availability.view",
            "call_slips.manage",
            "call_slips.view",
            "call_slips.view_self",
            "counseling.manage_assigned",
            "counseling.view_assigned",
            "document_branding.manage",
            "document_branding.view",
            "ecounseling.consent_self",
            "ecounseling.join_assigned",
            "ecounseling.join_self",
            "ecounseling.manage_media_assigned",
            "ecounseling.view_assigned",
            "ecounseling.view_self",
            "exit_interviews.manage_self",
            "exit_interviews.reopen",
            "exit_interviews.view",
            "exit_interviews.view_self",
            "feedback.submit_csm",
            "feedback.submit_customer_feedback",
            "feedback.view_csm",
            "feedback.view_customer_feedback",
            "good_moral.issue",
            "good_moral.manage",
            "good_moral.request_self",
            "good_moral.view",
            "good_moral.view_self",
            "graduate_tracer.manage_self",
            "graduate_tracer.view",
            "graduate_tracer.view_self",
            "institutional_designations.manage",
            "institutional_forms.manage",
            "institutional_forms.view",
            "inventory.manage_self",
            "inventory.view_self",
            "organization.manage",
            "organization.view",
            "platform_operations.manage",
            "platform_operations.view",
            "privacy_governance.manage",
            "privacy_governance.view",
            "reports.view",
            "referrals.manage",
            "referrals.view",
            "routine_interviews.manage_assigned",
            "routine_interviews.manage_self",
            "routine_interviews.view_assigned",
            "routine_interviews.view_self",
            "services.manage",
            "services.view",
            "shared_summaries.manage_assigned",
            "shared_summaries.view_assigned",
            "shared_summaries.view_self",
            "student_support.view",
        ]
    )
    assert schemas["Effect"]["enum"] == ["GRANT", "REVOKE"]
    assert schemas["AppointmentPolicy"]["enum"] == ["NONE", "OPTIONAL", "REQUIRED"]
    assert schemas["DeliveryMode"]["enum"] == ["IN_PERSON", "ONLINE"]
    assert schemas["ProviderRoleCode"]["enum"] == ["COUNSELOR", "GUIDANCE_SERVICES_STAFF"]
    assert schemas["Weekday"]["enum"] == [
        "MONDAY",
        "TUESDAY",
        "WEDNESDAY",
        "THURSDAY",
        "FRIDAY",
        "SATURDAY",
        "SUNDAY",
    ]
    assert schemas["AvailabilityModeScope"]["enum"] == ["ALL", "IN_PERSON", "ONLINE"]
    assert schemas["AppointmentStatus"]["enum"] == ["SCHEDULED", "CANCELLED"]
    assert schemas["CounselingEntryMode"]["enum"] == [
        "APPOINTMENT",
        "WALK_IN",
        "CALLED_IN",
        "REFERRED",
    ]
    assert "cancellation_cutoff_minutes" in schemas["ServiceResponse"]["properties"]

    response_schema_names = {
        "AccountSummaryResponse",
        "AccountDetailResponse",
        "MyProfileResponse",
        "CapabilityOverrideResponse",
        "SessionSummary",
        "TrustedSessionSummary",
        "CounselingEncounterResponse",
        "CounselingStudentResponse",
        "CounselingAssignedSharedSummaryResponse",
        "CounselingStudentSharedSummaryResponse",
        "StudentWorkspaceResponse",
        "CounselorWorkspaceResponse",
        "ConsentResponse",
        "MediaCaptureResponse",
        "ReferralDetailResponse",
        "ReferralActionResponse",
        "CallSlipOperationalResponse",
        "CallSlipStudentResponse",
        "DocumentBrandingProfileResponse",
        "ExitInterviewDetailResponse",
        "ExitInterviewSummaryResponse",
        "ExitInterviewPageResponse",
        "GraduateTracerDetailResponse",
        "GraduateTracerSummaryResponse",
        "GraduateTracerPageResponse",
    }
    forbidden_fields = {
        "password_hash",
        "profile_photo_object_key",
        "token_digest",
        "encrypted_secret",
        "code_hash",
        "turnstile_secret",
        "encryption_key",
        "daily_api_key",
        "daily_webhook_hmac",
        "provider_instance_id",
        "provider_artifact_id",
        "provider_session_id",
        "share_token",
        "s3_key",
        "transcript",
    }
    for schema_name in response_schema_names:
        assert forbidden_fields.isdisjoint(schemas[schema_name].get("properties", {}))

    serialized = json.dumps(schema).lower()
    assert not re.search(
        r"(?:password_hash|profile_photo_object_key|token_digest|encrypted_secret|code_hash|"
        r"turnstile_secret|encryption_key|daily_api_key|daily_webhook_hmac|share_token|s3_key)",
        serialized,
    )


def test_platform_operations_openapi_runtime_surface_and_secret_safety() -> None:
    schema = _generated_schema()

    read_only = {
        "/api/v1/platform/health": "platformOperationsHealth",
        "/api/v1/platform/environment": "platformOperationsEnvironment",
        "/api/v1/platform/commands": "platformOperationsCommandCatalog",
        "/api/v1/platform/maintenance": "platformOperationsGetMaintenance",
        "/api/v1/platform/email-deliveries/summary": "platformOperationsGetEmailDeliverySummary",
        "/api/v1/platform/email-deliveries": "platformOperationsListEmailDeliveries",
        "/api/v1/platform/activity": "platformOperationsListActivity",
    }
    for path, operation_id in read_only.items():
        path_item = schema["paths"][path]
        assert set(path_item) == {"get"}
        assert path_item["get"]["operationId"] == operation_id
        assert path_item["get"]["tags"] == ["platform-operations"]
        assert _response_statuses(path_item["get"]) >= {200, 401, 403}

    mutations = {
        ("/api/v1/platform/maintenance/enable", "post"): (
            "platformOperationsEnableMaintenance",
            {200, 401, 403, 409, 422},
        ),
        ("/api/v1/platform/maintenance/disable", "post"): (
            "platformOperationsDisableMaintenance",
            {200, 401, 403, 409},
        ),
        ("/api/v1/platform/maintenance/schedule", "put"): (
            "platformOperationsScheduleMaintenance",
            {200, 401, 403, 409, 422},
        ),
        ("/api/v1/platform/maintenance/schedule", "delete"): (
            "platformOperationsCancelMaintenanceSchedule",
            {200, 401, 403, 404},
        ),
        ("/api/v1/platform/email-deliveries/{delivery_id}/retry", "post"): (
            "platformOperationsRetryEmailDelivery",
            {200, 401, 403, 404, 409},
        ),
    }
    for (path, method), (operation_id, statuses) in mutations.items():
        operation = _operation(schema, path, method)
        assert operation["operationId"] == operation_id
        assert operation["tags"] == ["platform-operations"]
        assert _response_statuses(operation) >= statuses

    assert "/api/v1/platform/commands/run" not in schema["paths"]
    assert "/api/v1/platform/email-deliveries/retry" not in schema["paths"]

    schemas = schema["components"]["schemas"]
    safe_schema_names = {
        name
        for name in schemas
        if name.startswith(
            (
                "Platform",
                "Environment",
                "HealthCheck",
                "CommandCatalog",
                "Maintenance",
                "EmailDelivery",
                "TechnicalActivity",
            )
        )
    }
    serialized = json.dumps({name: schemas[name] for name in safe_schema_names}).lower()
    for forbidden in (
        "secret_key",
        "password",
        "redis_url",
        "bucket_name",
        "access_key",
        "smtp_host",
        "smtp_username",
        "daily_api_key",
        "daily_webhook_hmac",
        "turnstile_secret",
        "totp_encryption_key",
        "claim_token",
        "claim_expires_at",
        "recipient_email",
        "recipient_name",
        "notification_message",
        "notification_title",
        "email_body",
        "rendered_html",
        "metadata",
    ):
        assert forbidden not in serialized


def test_privacy_governance_openapi_is_purpose_built_and_has_no_delete_or_global_audit() -> None:
    schema = _generated_schema()

    read_operations = {
        ("/api/v1/privacy/processing-activities", "get"): (
            "privacyGovernanceListProcessingActivities",
            {200, 401, 403, 422},
        ),
        ("/api/v1/privacy/processing-activities/{processing_id}", "get"): (
            "privacyGovernanceGetProcessingActivity",
            {200, 401, 403, 404},
        ),
        ("/api/v1/privacy/processing-activities/{processing_id}/reviews", "get"): (
            "privacyGovernanceListReviews",
            {200, 401, 403, 404, 422},
        ),
        ("/api/v1/privacy/reviews/{review_id}", "get"): (
            "privacyGovernanceGetReview",
            {200, 401, 403, 404},
        ),
        ("/api/v1/privacy/incidents", "get"): (
            "privacyGovernanceListIncidents",
            {200, 401, 403, 422},
        ),
        ("/api/v1/privacy/incidents/{incident_id}", "get"): (
            "privacyGovernanceGetIncident",
            {200, 401, 403, 404},
        ),
        ("/api/v1/privacy/activity", "get"): (
            "privacyGovernanceListActivity",
            {200, 401, 403, 422},
        ),
    }
    for (path, method), (operation_id, statuses) in read_operations.items():
        operation = _operation(schema, path, method)
        assert operation["operationId"] == operation_id
        assert operation["tags"] == ["privacy-governance"]
        assert _response_statuses(operation) >= statuses

    mutation_operations = {
        (
            "/api/v1/privacy/processing-activities",
            "post",
        ): "privacyGovernanceCreateProcessingActivity",
        (
            "/api/v1/privacy/processing-activities/{processing_id}",
            "patch",
        ): "privacyGovernanceUpdateProcessingActivity",
        (
            "/api/v1/privacy/processing-activities/{processing_id}/retire",
            "post",
        ): "privacyGovernanceRetireProcessingActivity",
        (
            "/api/v1/privacy/processing-activities/{processing_id}/reviews",
            "post",
        ): "privacyGovernanceCreateReview",
        ("/api/v1/privacy/reviews/{review_id}", "patch"): "privacyGovernanceUpdateReview",
        (
            "/api/v1/privacy/reviews/{review_id}/resolve",
            "post",
        ): "privacyGovernanceResolveReview",
        ("/api/v1/privacy/incidents", "post"): "privacyGovernanceCreateIncident",
        (
            "/api/v1/privacy/incidents/{incident_id}",
            "patch",
        ): "privacyGovernanceUpdateIncident",
        (
            "/api/v1/privacy/incidents/{incident_id}/resolve",
            "post",
        ): "privacyGovernanceResolveIncident",
    }
    for (path, method), operation_id in mutation_operations.items():
        operation = _operation(schema, path, method)
        assert operation["operationId"] == operation_id
        assert operation["tags"] == ["privacy-governance"]
        assert {401, 403} <= _response_statuses(operation)

    for path in (
        "/api/v1/privacy/processing-activities/{processing_id}",
        "/api/v1/privacy/reviews/{review_id}",
        "/api/v1/privacy/incidents/{incident_id}",
    ):
        assert "delete" not in schema["paths"][path]

    assert "/api/v1/privacy/audit-events" not in schema["paths"]

    privacy_schemas = {
        name: value
        for name, value in schema["components"]["schemas"].items()
        if name.startswith(
            (
                "ProcessingActivity",
                "PrivacyReview",
                "PrivacyIncident",
                "PrivacyActivity",
            )
        )
    }
    serialized = json.dumps(privacy_schemas).lower()
    for forbidden in (
        "is_compliant",
        "attachment",
        "upload",
        "file_bytes",
        "raw_metadata",
        "ip_address",
        "user_agent",
        "password",
        "otp",
        "session_token",
    ):
        assert forbidden not in serialized
