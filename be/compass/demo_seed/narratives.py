"""Form narratives for the demo scenarios (data only).

Content is deliberately ordinary: study load, adjustment, finances, attendance, group work. It
avoids diagnoses, crises, and self-harm content; no scenario needs them to demonstrate COMPASS.
Every choice value is an existing enum value of its domain.
"""

from __future__ import annotations

from datetime import date

# --- Routine Interviews ----------------------------------------------------------------------

# Second-year Psychology Student adjusting to a heavier major-subject load (appointment-backed).
ADJUSTMENT_INTAKE = {
    "coping_with_college_challenges": (
        "I'm okay overall, but this semester feels heavier. The major subjects move quickly and "
        "by Friday I usually feel behind."
    ),
    "coping_remarks": "I would like help planning a realistic study schedule.",
    "college_experience": (
        "Mostly positive. I like my blockmates and the professors are approachable, but second "
        "year is more demanding than I expected."
    ),
    "reason_for_choosing_institution": (
        "It is close to home, my senior high adviser recommended the Psychology program, and the "
        "tuition is manageable for my family."
    ),
    "difficulties_encountered": (
        "Keeping up with readings for Developmental Psychology and Psychological Statistics while "
        "helping organize our society's events."
    ),
    "stress_anxiety_causes": (
        "Deadlines landing in the same week, recitations, and worrying about my grade in "
        "Psychological Statistics."
    ),
    "stress_anxiety_management": (
        "I make a to-do list, talk with my friends, and try to sleep earlier. Sometimes I walk "
        "around the plaza to clear my head."
    ),
    "family_description": (
        "I live with my parents and my younger brother. My father works at the municipal hall and "
        "my mother runs a small home bakery. They are supportive and hope I keep my scholarship."
    ),
    "concerns": ["ACADEMIC", "SLEEPING_PROBLEMS"],
    "other_concern_specification": "",
    "concerns_explanation": (
        "I need to keep a grade average that retains my academic scholarship. I missed two "
        "requirements when our society's event overlapped with midterms, and I have been "
        "sleeping late to catch up."
    ),
    "college_adjustment_and_peer_group": (
        "I have a small barkada from my block and we review together before quizzes. I am still "
        "learning to say no to extra organization tasks."
    ),
    "academic_goals": (
        "Keep my scholarship and finish the semester without incomplete grades. Review "
        "statistics every week instead of cramming."
    ),
    "career_goals": (
        "Pass the Psychometrician Licensure Examination and work in guidance or human resources."
    ),
}
ADJUSTMENT_EVALUATION = {
    "academic_adjustment_rating": 6,
    "physical_adjustment_rating": 7,
    "social_adjustment_rating": 8,
    "spiritual_adjustment_rating": 7,
    "financial_adjustment_rating": 6,
    "emotional_adjustment_rating": 6,
    "other_adjustment": "Heavier major-subject load; time management is the main gap.",
    "special_concern": "Scholarship-retention pressure and late nights. No safety concerns noted.",
    "recommendations": (
        "Fixed weekly review blocks for Psychological Statistics; agree on unavailable exam weeks "
        "with society officers; aim for lights-out before 11 PM on school nights; follow-up "
        "session in about two weeks."
    ),
}
ADJUSTMENT_SHARED_SUMMARY = (
    "Thank you for meeting with the Guidance and Counseling Office.\n\n"
    "We talked about balancing your major subjects with your organization work. Next steps we "
    "agreed on:\n\n"
    "1. Block two fixed review periods each week for Psychological Statistics.\n"
    "2. Tell your society officers ahead of time which exam weeks you are unavailable.\n"
    "3. Try to sleep before 11 PM on school nights.\n\n"
    "Your follow-up session is already scheduled. You may book an earlier time if you need to."
)

# Fourth-year Information Systems Student who walked in about a capstone workload dispute.
WALK_IN_INTAKE = {
    "coping_with_college_challenges": (
        "Mostly fine. Capstone takes most of my time and I'm tired on weekdays."
    ),
    "coping_remarks": "I walked in because our capstone group disagreed about workload.",
    "college_experience": (
        "Good. I learned a lot, especially in database and systems analysis subjects."
    ),
    "reason_for_choosing_institution": (
        "My cousin finished the same program and recommended it, and it is near our town."
    ),
    "difficulties_encountered": (
        "Coordinating with groupmates who have part-time jobs, and following lectures in large "
        "rooms."
    ),
    "stress_anxiety_causes": (
        "Capstone deadlines, the pre-oral defense schedule, and uneven task distribution."
    ),
    "stress_anxiety_management": (
        "Basketball on weekends, music, and tracking tasks on our shared project board."
    ),
    "family_description": (
        "My parents farm rice in Labo and my mother also works at the barangay day-care center. "
        "My older sister works in Manila and helps with my tuition."
    ),
    "concerns": ["ACADEMIC", "CLASSMATES"],
    "other_concern_specification": "",
    "concerns_explanation": (
        "Two members of our capstone group rarely attend meetings, so I end up doing most of the "
        "documentation."
    ),
    "college_adjustment_and_peer_group": (
        "I get along with most classmates. My closest friends are from the varsity team."
    ),
    "academic_goals": "Pass the capstone defense this semester and graduate on time.",
    "career_goals": "Work as a systems analyst or IT support specialist in the province.",
}
WALK_IN_EVALUATION = {
    "academic_adjustment_rating": 7,
    "physical_adjustment_rating": 8,
    "social_adjustment_rating": 6,
    "spiritual_adjustment_rating": 7,
    "financial_adjustment_rating": 7,
    "emotional_adjustment_rating": 7,
    "other_adjustment": "Group-work conflict is affecting motivation.",
    "special_concern": "Prefers front seating during lectures (noted in Inventory).",
    "recommendations": (
        "Used a workload-agreement worksheet for the capstone group; advised raising the concern "
        "with the capstone adviser; optional follow-up after the pre-oral defense."
    ),
}
WALK_IN_SUMMARY_DRAFT = (
    "We discussed ways to divide capstone tasks more fairly and how to raise the concern with "
    "your capstone adviser. (Draft — not yet shared.)"
)

# Third-year Hospitality Management Student seen after a Program Chair referral.
REFERRED_INTAKE = {
    "coping_with_college_challenges": (
        "Not so good these past weeks. I had to go home often to help my family."
    ),
    "coping_remarks": "I want to catch up on my laboratory requirements.",
    "college_experience": "I enjoy the practical classes. Hospitality is really what I want.",
    "reason_for_choosing_institution": (
        "Affordable tuition, and the program has good on-the-job training partners."
    ),
    "difficulties_encountered": (
        "Travel costs on laboratory days and missing classes when I go home."
    ),
    "stress_anxiety_causes": (
        "Missed requirements and not having enough money for laboratory ingredients."
    ),
    "stress_anxiety_management": (
        "Talking with my older sister and praying. I also work on requirements at night."
    ),
    "family_description": (
        "My parents are farmers in our community in the uplands of Labo. I am the second of four "
        "children and I stay in a boarding house near campus."
    ),
    "concerns": ["FINANCIAL", "ACADEMIC", "DORM_BOARDING_HOUSE"],
    "other_concern_specification": "",
    "concerns_explanation": (
        "Our harvest was delayed so money is tight this month, and I had to move to a new "
        "boarding house."
    ),
    "college_adjustment_and_peer_group": (
        "Classmates help me, but I'm shy about asking for help all the time."
    ),
    "academic_goals": ("Complete my missed laboratory logbook and pass Food and Beverage Service."),
    "career_goals": "Work in a resort or hotel in Bicol, then open a small restaurant someday.",
}
REFERRED_FOLLOW_UP_SUMMARY = (
    "Thank you for coming back for your follow-up session.\n\n"
    "We reviewed your plan for the missed laboratory work. Next steps:\n\n"
    "1. Ask your Food and Beverage Service instructor for a make-up laboratory schedule.\n"
    "2. Submit your completed practical logbook pages one week at a time.\n"
    "3. Review the student financial assistance information we shared and apply if you qualify.\n\n"
    "Please visit the office again after midterms, or earlier if things change."
)

# --- Referrals and Call Slips ----------------------------------------------------------------

REFERRED_REFERRAL = {
    "course_year_block": "BSHM 3-B",
    "reason": (
        "Missed three consecutive laboratory sessions in Food and Beverage Service and has not "
        "submitted the practical logbook. Appeared withdrawn during the last class. Requesting a "
        "guidance interview to understand the student's situation and the support needed."
    ),
    "referrer_name": "Prof. Liza R. Ponce, BSHM Program Chair",
}
REFERRED_DUPLICATE_VOID_REASON = (
    "Duplicate entry: the same Program Chair referral slip was recorded twice. See {code}."
)
ACTIVE_REFERRAL = {
    "course_year_block": "BAELS 2-A",
    "reason": (
        "Absent in five class meetings over the past three weeks and missing two graded essays in "
        "Introduction to Linguistics. The adviser has not been able to reach the student outside "
        "class and requests a guidance interview."
    ),
    "referrer_name": "Ms. Joanna M. Villaflor, Class Adviser, BAELS 2-A",
}
HISTORICAL_REFERRAL = {
    "course_year_block": "BSIS 3-A",
    "reason": (
        "Repeated late submissions in Systems Analysis and Design and three missed consultation "
        "schedules. The instructor requests a guidance interview about workload and attendance."
    ),
    "referrer_name": "Mr. Dexter A. Fajardo, Instructor, BSIS",
}
CALL_SLIP_ACTION_REMARKS = "Call slip issued through the class adviser."
VOIDED_CALL_SLIP_REASON = (
    "Student had already booked a counseling appointment for the same week; interview permit "
    "withdrawn."
)

# --- Exit Interviews -------------------------------------------------------------------------

_SELF_ASSESSMENT_CODES = (
    "PRIDE_CONFIDENCE_CNSC",
    "ACADEMIC_RECREATION_BALANCE",
    "HOLISTIC_PERSONAL_WELL_BEING",
    "INTEGRATE_KNOWLEDGE_EXPERIENCE",
    "CAREER_GOAL_CLARITY",
    "SELF_ESTEEM",
    "SELF_AWARENESS",
    "COPE_WITH_PRESSURES",
    "DEAL_WITH_DIFFERENT_WALKS",
    "LEADERSHIP",
    "COMMUNICATION_SKILLS",
    "CIVIC_MINDEDNESS",
    "INITIATIVE",
    "DECISION_MAKING",
    "RELATIONSHIP_WITH_GOD",
)
_COLLEGE_FEEDBACK_CODES = (
    "DEAN_AVAILABILITY",
    "DEAN_OPEN_MINDEDNESS",
    "DEAN_CONCERN_FOR_STUDENTS",
    "DEAN_COMMITMENT",
    "DEAN_APPROACHABILITY",
    "PROGRAM_CHAIR_AVAILABILITY",
    "PROGRAM_CHAIR_APPROACHABILITY",
    "PROGRAM_CHAIR_CONCERN_FOR_STUDENTS",
    "FACULTY_AVAILABILITY",
    "FACULTY_APPROACHABILITY",
    "FACULTY_KNOWLEDGE_SUBJECT_MATTER",
    "FACULTY_TEACHING_SKILLS",
    "CURRICULUM_RELEVANCE_SUBJECTS",
    "CURRICULUM_SYSTEMATIC_SEQUENCING",
    "CURRICULUM_COMPLETENESS",
    "GUIDANCE_COUNSELOR_AVAILABILITY",
    "GUIDANCE_COUNSELOR_APPROACHABILITY",
    "GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS",
    "GUIDANCE_COUNSELOR_EFFICIENCY",
    "OFFICE_STAFF_SERVICE_ORIENTED",
    "OFFICE_STAFF_AVAILABILITY",
    "OFFICE_STAFF_CONCERN_FOR_STUDENTS",
    "OFFICE_STAFF_APPROACHABILITY",
    "FACILITIES_MAINTENANCE_CONDITION",
    "FACILITIES_AVAILABILITY",
    "FACILITIES_COMPLETENESS",
)


def _ratings(codes: tuple[str, ...], values: str) -> list[dict[str, object]]:
    digits = [int(value) for value in values.split()]
    if len(digits) > len(codes):
        raise RuntimeError("more ratings than source items")
    # A draft may rate only the first items; submitted interviews rate all of them.
    return [
        {"item_code": code, "rating": rating}
        for code, rating in zip(codes[: len(digits)], digits, strict=True)
    ]


def _exit_interview(
    *,
    completion: str,
    learning: list[str],
    career_modes: list[str],
    work: list[str],
    study: list[str],
    comments: dict[str, str],
    self_ratings: str,
    college_ratings: str,
    extra_terms: int | None = None,
    delay_reasons: list[str] | None = None,
    delay_other: str = "",
) -> dict[str, object]:
    return {
        "program_completion": completion,
        "extra_terms_count": extra_terms,
        "delay_reasons": delay_reasons or [],
        "delay_other": delay_other,
        "significant_learning_experiences": learning,
        "significant_learning_other": "",
        "career_modes": career_modes,
        "work_choices": work,
        "study_choices": study,
        **{
            name: comments.get(name, "")
            for name in (
                "dean_comments",
                "program_chair_comments",
                "faculty_comments",
                "curriculum_comments",
                "guidance_counselor_comments",
                "office_staff_comments",
                "facilities_comments",
                "suggestions_recommendations",
            )
        },
        "self_assessment_ratings": _ratings(_SELF_ASSESSMENT_CODES, self_ratings),
        "college_feedback_ratings": _ratings(_COLLEGE_FEEDBACK_CODES, college_ratings),
    }


ALUMNI_EXIT_INTERVIEW = _exit_interview(
    completion="ACCORDING_TO_SCHEDULE",
    learning=["INTELLECTUAL_GROWTH", "RESPONSIBILITY", "TIME_MANAGEMENT"],
    career_modes=["WORK"],
    work=["RELATED_FIELD"],
    study=[],
    comments={
        "dean_comments": "Visible during college activities and easy to approach.",
        "program_chair_comments": "Very helpful during practice teaching deployment.",
        "faculty_comments": "Most instructors gave clear feedback on our lesson plans.",
        "curriculum_comments": "More classroom immersion before the final year would help.",
        "guidance_counselor_comments": (
            "The pre-deployment orientation eased my worries about practice teaching."
        ),
        "office_staff_comments": "Quick transactions except during enrollment peaks.",
        "facilities_comments": "The speech laboratory needs more working headsets.",
        "suggestions_recommendations": "Offer licensure review sessions earlier in fourth year.",
    },
    self_ratings="5 4 4 5 5 4 4 4 5 4 5 4 4 4 5",
    college_ratings="4 4 5 4 5 5 5 4 4 4 5 4 4 4 3 4 5 5 4 4 3 4 4 3 3 3",
)
RECENT_GRADUATE_EXIT_INTERVIEW = _exit_interview(
    completion="ACCORDING_TO_SCHEDULE",
    learning=["INDEPENDENCE", "INTERPERSONAL_RELATIONS", "WORKING_UNDER_PRESSURE"],
    career_modes=["WORK", "STUDY"],
    work=["RELATED_FIELD"],
    study=["RELATED_FIELD"],
    comments={
        "dean_comments": "Supportive of student media projects.",
        "program_chair_comments": "Helped us find internship partners in local government.",
        "faculty_comments": "Fieldwork-based classes were the most valuable.",
        "curriculum_comments": "Research subjects could be spread across two semesters.",
        "guidance_counselor_comments": "Career orientation before internship was useful.",
        "office_staff_comments": "Generally helpful; forms were sometimes hard to find.",
        "facilities_comments": "The editing room needs updated computers.",
        "suggestions_recommendations": "Partner with more community radio stations for OJT.",
    },
    self_ratings="4 3 4 5 4 4 5 4 5 4 5 5 4 4 4",
    college_ratings="4 4 4 4 4 5 5 5 4 4 5 4 4 3 4 4 4 4 4 4 4 4 4 2 3 3",
)
# Delayed graduate finishing this first semester; the draft is still being filled in.
GRADUATING_EXIT_INTERVIEW_DRAFT = _exit_interview(
    completion="WITH_SOME_DELAY",
    extra_terms=1,
    delay_reasons=["OTHER"],
    delay_other="Took a one-semester leave of absence to help run the family store.",
    learning=["RESPONSIBILITY", "SETTING_PRIORITIES"],
    career_modes=["WORK"],
    work=["RELATED_FIELD", "FAMILY_BUSINESS"],
    study=[],
    comments={
        "dean_comments": "Understanding when I returned from my leave.",
        "program_chair_comments": "Helped me map my remaining subjects.",
    },
    self_ratings="4 4 4 4 5 4 4 5 4 3",
    college_ratings="4 4 5 4 4 5 5 5",
)

# --- Good Moral --------------------------------------------------------------------------------

# The certificate template supplies the words "year" and "semester" itself.
GOOD_MORAL_CURRENT = {
    "year_level": "3rd",
    "semester": "First",
    "college": "Business and Public Administration",
}
GOOD_MORAL_CURRENT_RECEIPT = {"official_receipt_number": "DEMO-OR-0142", "amount": "50.00"}
GOOD_MORAL_DUPLICATE_CANCEL_REASON = "Duplicate request submitted by mistake."
GRADUATING_GOOD_MORAL = {"year_level": "5th", "semester": "First"}
RECENT_GRADUATE_GOOD_MORAL = {
    "degree": "Bachelor of Science in Development Communication",
    "major": "",
    "graduation_date": date(2026, 6, 26),
    "official_receipt_number": "DEMO-OR-0087",
    "amount": "50.00",
}
ALUMNI_GOOD_MORAL = {
    "degree": "Bachelor of Secondary Education",
    "major": "English",
    "graduation_date": date(2025, 6, 27),
}

# --- Graduate Tracer -------------------------------------------------------------------------

ALUMNI_TRACER = {
    "civil_status": "SINGLE",
    "sex": "FEMALE",
    "region_of_origin": "REGION_5",
    "province": "Camarines Norte",
    "residence_location": "MUNICIPALITY",
    "undergraduate_degree_reasons": ["PASSION_PROFESSION", "AFFORDABLE", "COURSE_AVAILABILITY"],
    "current_employment_state": "EMPLOYED",
    "present_employment_status": "CONTRACTUAL",
    "present_occupation": "Junior High School English Teacher",
    "employer_business_line": "EDUCATION",
    "place_of_work": "LOCAL",
    "first_job_after_college": True,
    "reasons_for_staying_on_job": ["RELATED_COURSE", "PROXIMITY_RESIDENCE"],
    "first_job_related_to_course": True,
    "reasons_for_accepting_first_job": ["RELATED_SPECIAL_SKILLS", "PROXIMITY_RESIDENCE"],
    "first_job_duration": "SEVEN_TO_ELEVEN_MONTHS",
    "first_job_source": "RECOMMENDED",
    "time_to_first_job": "ONE_TO_SIX_MONTHS",
    "first_job_level": "PROFESSIONAL_TECHNICAL_SUPERVISORY",
    "current_job_level": "PROFESSIONAL_TECHNICAL_SUPERVISORY",
    "initial_gross_monthly_earning": "FROM_15000_TO_LT_20000",
    "curriculum_relevant_to_first_job": True,
    "useful_competencies": ["COMMUNICATION", "HUMAN_RELATIONS", "CRITICAL_THINKING"],
    "curriculum_improvement_suggestions": (
        "More practice in classroom management and assessment design before deployment."
    ),
    "education": [
        {
            "degree_and_specialization": "Bachelor of Secondary Education major in English",
            "college_or_university": "University of Camarines Norte",
            "year_graduated": 2025,
            "honors_or_awards": "",
        }
    ],
    "professional_exams": [
        {
            "examination_name": "Licensure Examination for Professional Teachers (Secondary)",
            "date_taken": date(2025, 9, 28),
            "rating": "Passed",
        }
    ],
    "trainings": [
        {
            "title": "Differentiated Instruction in the English Classroom",
            "duration_and_credits": "3 days",
            "institution": "Schools Division Office seminar",
        }
    ],
}
# Started a few days ago; employment answers are still blank.
RECENT_GRADUATE_TRACER_DRAFT = {
    "civil_status": "SINGLE",
    "sex": "MALE",
    "region_of_origin": "REGION_5",
    "province": "Camarines Norte",
    "residence_location": "MUNICIPALITY",
    "undergraduate_degree_reasons": ["PASSION_PROFESSION", "ROLE_MODEL"],
    "education": [
        {
            "degree_and_specialization": "Bachelor of Science in Development Communication",
            "college_or_university": "University of Camarines Norte",
            "year_graduated": 2026,
            "honors_or_awards": "",
        }
    ],
}

# --- Customer Feedback and CSM ---------------------------------------------------------------


def _customer_ratings(values: str) -> dict[str, int]:
    names = (
        "personnel_accommodating_rating",
        "personnel_job_knowledge_rating",
        "personnel_flexibility_rating",
        "personnel_information_accuracy_rating",
        "personnel_appearance_rating",
        "personnel_commitment_delivery_rating",
        "office_location_rating",
        "office_cleanliness_rating",
        "office_environment_rating",
        "office_hours_rating",
        "personnel_availability_rating",
        "overall_satisfaction_rating",
    )
    digits = [int(value) for value in values.split()]
    if len(digits) != len(names):
        raise RuntimeError("Customer Feedback needs all twelve ratings")
    return dict(zip(names, digits, strict=True))


def _csm_ratings(values: str) -> dict[str, int]:
    digits = [int(value) for value in values.split()]
    if len(digits) != 9:
        raise RuntimeError("CSM needs all nine SQD ratings")
    return {f"sqd{index}": value for index, value in enumerate(digits)}


CUSTOMER_FEEDBACK = {
    "second_year": {
        "services_received": ["COUNSELING"],
        "talked_to_guidance_counselor": True,
        "office_visit_count": 2,
        "transaction_duration": "About 50 minutes",
        "additional_feedback": (
            "The counselor listened well and helped me make a realistic study plan."
        ),
        "future_service_improvement": "A reminder the day before the appointment would help.",
        "course_year": "BS Psychology 2",
        **_customer_ratings("5 5 4 5 5 5 3 4 4 4 4 5"),
    },
    "good_moral": {
        "services_received": ["REQUEST_FOR_CERTIFICATION"],
        "talked_to_guidance_counselor": False,
        "accommodated_by": "CLERK_PERSONNEL",
        "office_visit_count": 1,
        "transaction_duration": "About 15 minutes to file; released after two days",
        "additional_feedback": "Clear instructions and polite staff.",
        "future_service_improvement": "Post the certificate requirements near the office door.",
        "course_year": "BS Accountancy 3",
        **_customer_ratings("4 4 4 5 4 4 4 5 4 3 4 4"),
    },
    "recent_graduate": {
        "services_received": ["REQUEST_FOR_CERTIFICATION"],
        "talked_to_guidance_counselor": False,
        "accommodated_by": "STUDENT_ASSISTANT",
        "office_visit_count": 2,
        "transaction_duration": "Two days from request to release",
        "additional_feedback": "Friendly assistance, though I had to come back once.",
        "future_service_improvement": "Allow graduates to request certificates online.",
        "course_year": "BS Development Communication (graduate)",
        **_customer_ratings("4 3 3 4 4 4 3 4 4 3 3 4"),
    },
    "referred": {
        "services_received": ["COUNSELING"],
        "talked_to_guidance_counselor": True,
        "office_visit_count": 3,
        "transaction_duration": "About one hour",
        "additional_feedback": "I felt comfortable explaining my situation.",
        "future_service_improvement": "",
        "course_year": "BSHM 3",
        **_customer_ratings("5 5 5 5 4 5 4 4 5 4 5 5"),
    },
}

CLIENT_SATISFACTION = (
    {
        "persona": "second_year",
        "client_type": "CITIZEN",
        "sex": "FEMALE",
        "age": 19,
        "region_of_residence": "Region V - Bicol",
        "service_availed": "Counseling",
        "cc1": 1,
        "cc2": 2,
        "cc3": 1,
        "suggestions": "Clear instructions on how to book a follow-up session.",
        **_csm_ratings("5 4 5 4 5 5 4 5 4"),
    },
    {
        "persona": "good_moral",
        "client_type": "CITIZEN",
        "sex": "FEMALE",
        "age": 21,
        "region_of_residence": "Region V - Bicol",
        "service_availed": "Issuance of Good Moral Certificate",
        "cc1": 2,
        "cc2": 2,
        "cc3": 2,
        "suggestions": "Longer office hours during enrollment week.",
        **_csm_ratings("4 4 4 3 4 4 4 5 4"),
    },
    {
        "persona": "referred",
        "client_type": "CITIZEN",
        "sex": "MALE",
        "age": 20,
        "region_of_residence": "Region V - Bicol",
        "service_availed": "Counseling (referral follow-up)",
        "cc1": 3,
        "cc2": 1,
        "cc3": 1,
        "suggestions": "More chairs in the waiting area.",
        **_csm_ratings("5 5 4 5 5 4 5 5 5"),
    },
    {
        "persona": "recent_graduate",
        "client_type": "CITIZEN",
        "sex": "MALE",
        "age": 22,
        "region_of_residence": "Region V - Bicol",
        "service_availed": "Issuance of Good Moral Certificate (graduate)",
        "cc1": 4,
        "cc2": 5,
        "cc3": 4,
        "suggestions": "Please allow requesting certificates online.",
        **_csm_ratings("4 3 4 4 4 0 4 4 4"),
    },
)


__all__ = [
    "ACTIVE_REFERRAL",
    "ADJUSTMENT_EVALUATION",
    "ADJUSTMENT_INTAKE",
    "ADJUSTMENT_SHARED_SUMMARY",
    "ALUMNI_EXIT_INTERVIEW",
    "ALUMNI_GOOD_MORAL",
    "ALUMNI_TRACER",
    "CALL_SLIP_ACTION_REMARKS",
    "CLIENT_SATISFACTION",
    "CUSTOMER_FEEDBACK",
    "GOOD_MORAL_CURRENT",
    "GOOD_MORAL_CURRENT_RECEIPT",
    "GOOD_MORAL_DUPLICATE_CANCEL_REASON",
    "GRADUATING_EXIT_INTERVIEW_DRAFT",
    "GRADUATING_GOOD_MORAL",
    "HISTORICAL_REFERRAL",
    "RECENT_GRADUATE_EXIT_INTERVIEW",
    "RECENT_GRADUATE_GOOD_MORAL",
    "RECENT_GRADUATE_TRACER_DRAFT",
    "REFERRED_DUPLICATE_VOID_REASON",
    "REFERRED_FOLLOW_UP_SUMMARY",
    "REFERRED_INTAKE",
    "REFERRED_REFERRAL",
    "VOIDED_CALL_SLIP_REASON",
    "WALK_IN_EVALUATION",
    "WALK_IN_INTAKE",
    "WALK_IN_SUMMARY_DRAFT",
]
