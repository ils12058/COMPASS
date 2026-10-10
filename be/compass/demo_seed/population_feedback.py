"""Two additional Feedback/CSM patterns with real secondary Encounter provenance."""

from django.db import transaction

from compass.counseling.models import CounselingEncounter
from compass.feedback.models import ClientSatisfactionResponse, CustomerFeedbackResponse
from compass.feedback.services import create_csm_response, create_customer_feedback

from .feedback_content import matching_feedback
from .narratives import _csm_ratings, _customer_ratings
from .publications import _demo_feedback_opportunity, _stamp_demo_feedback_marker
from .support import align_timestamps

CUSTOMER_FEEDBACK = {
    "population_27": {
        "services_received": ["COUNSELING"],
        "talked_to_guidance_counselor": True,
        "office_visit_count": 1,
        "transaction_duration": "About 45 minutes",
        "additional_feedback": "Comparing internship options helped me plan my next steps.",
        "future_service_improvement": "Offer a short career planning worksheet before the visit.",
        "course_year": "BSBA 3",
        **_customer_ratings("4 5 4 4 5 4 3 4 4 4 5 4"),
    },
    "population_38": {
        "services_received": ["COUNSELING"],
        "talked_to_guidance_counselor": True,
        "office_visit_count": 1,
        "transaction_duration": "About 45 minutes",
        "additional_feedback": "",
        "future_service_improvement": "",
        "course_year": "BS Biology 3",
        **_customer_ratings("4 4 4 4 4 4 4 4 4 4 4 4"),
    },
}
CLIENT_SATISFACTION = (
    {
        "persona": "population_27",
        "client_type": "CITIZEN",
        "sex": "FEMALE",
        "age": 20,
        "region_of_residence": "Region V - Bicol",
        "service_availed": "Counseling (career planning)",
        "cc1": 1,
        "cc2": 2,
        "cc3": 1,
        "suggestions": "More sample internship plans would help.",
        **_csm_ratings("4 5 4 4 4 5 3 4 4"),
    },
    {
        "persona": "population_38",
        "client_type": "CITIZEN",
        "sex": "MALE",
        "age": 20,
        "region_of_residence": "Region V - Bicol",
        "service_availed": "Counseling (elective planning)",
        "cc1": 2,
        "cc2": 2,
        "cc3": 2,
        "suggestions": "",
        **_csm_ratings("4 4 4 4 4 4 4 4 4"),
    },
)


def seed_population_feedback(session):
    with transaction.atomic():
        for csm in CLIENT_SATISFACTION:
            key = csm["persona"]
            encounter = CounselingEncounter.objects.get(student=session.user(key))
            opportunity = _demo_feedback_opportunity(session, key)
            submitted = max(session.timeline.past(6, 18), encounter.ended_at)
            values = CUSTOMER_FEEDBACK[key]
            customer = next(
                matching_feedback(
                    CustomerFeedbackResponse.objects.filter(
                        respondent_name_snapshot=session.user(key).get_full_name()
                    ),
                    "additional_feedback",
                    values["additional_feedback"],
                ),
                None,
            )
            created = customer is None
            if created:
                customer = create_customer_feedback(
                    student=session.user(key),
                    opportunity_id=opportunity.pk,
                    values=dict(values),
                    context=session.as_user(key),
                )
                align_timestamps(customer, submitted_at=submitted)
            session.record("Customer Feedback", created=created)
            values = {name: value for name, value in csm.items() if name != "persona"}
            response = next(
                matching_feedback(
                    ClientSatisfactionResponse.objects.filter(
                        service_availed=values["service_availed"],
                        sex=values["sex"],
                        age=values["age"],
                    ),
                    "suggestions",
                    values["suggestions"],
                ),
                None,
            )
            created = response is None
            if created:
                response = create_csm_response(
                    student=session.user(key),
                    opportunity_id=opportunity.pk,
                    values=values,
                    context=session.as_user(key),
                )
                align_timestamps(response, submitted_at=submitted)
            session.record("CSM responses", created=created)
            _stamp_demo_feedback_marker(
                opportunity,
                customer_feedback_at=customer.submitted_at,
                csm_at=response.submitted_at,
            )
