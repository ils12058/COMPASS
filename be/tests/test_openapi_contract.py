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
    "authGetCsrf",
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
    "accountsList",
    "accountsCreate",
    "accountsGet",
    "accountsUpdateIdentity",
    "accountsDisable",
    "accountsEnable",
    "accountsChangeRole",
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
        "accounts",
        "organization",
        "services",
        "availability",
        "appointments",
        "counseling",
        "academic-years",
        "institutional-forms",
        "inventory",
        "routine-interviews",
        "referrals",
        "call-slips",
        "e-counseling",
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
        "ActivityPageResponse",
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
    }
    assert expected_schemas <= schemas.keys()
    assert schemas["AccountSummaryResponse"]["properties"]["id"]["format"] == "uuid"
    assert schemas["AccountSummaryResponse"]["properties"]["created_at"]["format"] == "date-time"
    assert schemas["AccountListResponse"]["properties"]["items"]["type"] == "array"
    assert schemas["APIErrorResponse"]["properties"]["error"]["$ref"].endswith("/APIErrorDetail")
    assert schemas["APIErrorDetail"]["properties"]["details"]["anyOf"]
    assert _operation(schema, "/api/v1/accounts", "post")["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/AccountCreateRequest")
    assert _operation(schema, "/api/v1/auth/login", "post")["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/LoginRequest")
    assert _operation(schema, "/api/v1/auth/password/request", "post")["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/PasswordAccessRequest")
    assert _operation(schema, "/api/v1/auth/password/confirm", "post")["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/PasswordAccessConfirmRequest")
    assert "password" not in schemas["AccountCreateRequest"]["properties"]
    assert {"email", "first_name", "last_name", "role"} <= set(
        schemas["AccountCreateRequest"]["required"]
    )
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
    assert _response_statuses(_operation(schema, "/api/v1/accounts", "post")) >= {
        201,
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
            "ecounseling.consent_self",
            "ecounseling.join_assigned",
            "ecounseling.join_self",
            "ecounseling.manage_media_assigned",
            "ecounseling.view_assigned",
            "ecounseling.view_self",
            "institutional_forms.manage",
            "institutional_forms.view",
            "inventory.manage_self",
            "inventory.view_self",
            "organization.manage",
            "organization.view",
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
