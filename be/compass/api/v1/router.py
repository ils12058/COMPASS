"""Django Ninja API object and version-one route registration."""

from django.conf import settings
from ninja import NinjaAPI

from compass.account_management.api import router as account_management_router
from compass.activity.api import router as activity_router
from compass.api.v1.health import router as health_router
from compass.appointments.api import router as appointments_router
from compass.authentication.api import router as authentication_router
from compass.availability.api import router as availability_router
from compass.common.errors import register_exception_handlers
from compass.counseling.api import router as counseling_router
from compass.ecounseling.api import daily_router
from compass.ecounseling.api import router as ecounseling_router
from compass.institutional_forms.api import router as institutional_forms_router
from compass.inventory.api import router as inventory_router
from compass.organization.academic_years_api import router as academic_years_router
from compass.organization.api import router as organization_router
from compass.routine_interviews.api import router as routine_interviews_router
from compass.service_catalog.api import router as service_catalog_router

api = NinjaAPI(
    title="COMPASS API",
    version="1.0.0",
    description="The version-one backend API for COMPASS.",
    openapi_extra={
        "tags": [
            {"name": "health", "description": "Process liveness and dependency readiness."},
            {"name": "auth", "description": "Cookie-based authentication and account security."},
            {"name": "activity", "description": "Authenticated self-activity projections."},
            {"name": "accounts", "description": "Capability-authorized account management."},
            {
                "name": "organization",
                "description": "Organizational structure and default responsibility routing.",
            },
            {
                "name": "services",
                "description": "Guidance and Counseling Office service catalog configuration.",
            },
            {
                "name": "availability",
                "description": "Office and provider scheduling Availability configuration.",
            },
            {
                "name": "appointments",
                "description": "Shared Student and provider Appointment reservations.",
            },
            {
                "name": "counseling",
                "description": "Assigned records of actual Counseling encounters.",
            },
            {
                "name": "academic-years",
                "description": "Institution-wide current Academic Year configuration.",
            },
            {
                "name": "institutional-forms",
                "description": "QMS-approved controlled-form revision metadata used by COMPASS.",
            },
            {
                "name": "inventory",
                "description": "Student annual Individual Inventory self-service.",
            },
            {
                "name": "routine-interviews",
                "description": (
                    "Interaction-specific Student Intake and assigned Counselor Evaluation."
                ),
            },
            {
                "name": "e-counseling",
                "description": "Secure ONLINE Counseling workspace and Daily provider boundary.",
            },
        ]
    },
    openapi_url="/openapi.json" if settings.API_DOCS_ENABLED else None,
    docs_url="/docs" if settings.API_DOCS_ENABLED else None,
)
api.add_router("/health", health_router)
api.add_router("/auth", authentication_router)
api.add_router("/me", activity_router)
api.add_router("/accounts", account_management_router)
api.add_router("/organization", organization_router)
api.add_router("/services", service_catalog_router)
api.add_router("/availability", availability_router)
api.add_router("/appointments", appointments_router)
api.add_router("/counseling", counseling_router)
api.add_router("/academic-years", academic_years_router)
api.add_router("/institutional-forms", institutional_forms_router)
api.add_router("/inventory", inventory_router)
api.add_router("/routine-interviews", routine_interviews_router)
api.add_router("/e-counseling", ecounseling_router)
api.add_router("/integrations/daily", daily_router)
register_exception_handlers(api)
