"""Additional form answer patterns, separate from identity and workflow orchestration."""

from copy import deepcopy

from . import narratives

EXIT_COMMENTS = (
    (
        "Internship supervisors explained how classroom work connects to practice.",
        "Add more supervised laboratory time before internship.",
    ),
    (
        "Group research improved my confidence presenting unfamiliar findings.",
        "Publish clearer advising schedules during enrollment.",
    ),
    (
        "Community projects taught me to organize tasks and listen to different views.",
        "Provide more study spaces for students with long commutes.",
    ),
    (
        "Peer mentoring helped me adjust to the workload in my final year.",
        "Keep career consultations available before final examinations.",
    ),
)


def exit_answers(index: int, *, depth: str = "SUBMITTED"):
    values = deepcopy(narratives.RECENT_GRADUATE_EXIT_INTERVIEW)
    experience, suggestion = EXIT_COMMENTS[index % len(EXIT_COMMENTS)]
    values.update(
        faculty_comments=experience,
        suggestions_recommendations=suggestion,
        program_chair_comments="Advising helped me plan my remaining subjects.",
        guidance_counselor_comments="Career planning sessions helped me compare options.",
        facilities_comments="More reliable laboratory equipment would help.",
    )
    for field in ("self_assessment_ratings", "college_feedback_ratings"):
        for position, row in enumerate(values[field]):
            row["rating"] = 3 + (position + index) % 3
    if depth == "EARLY":
        return {"program_completion": "ACCORDING_TO_SCHEDULE", "faculty_comments": experience}
    return values


def tracer_answers(member, program):
    values = deepcopy(narratives.ALUMNI_TRACER)
    values.update(
        sex=member.persona.sex,
        education=[
            {
                "degree_and_specialization": program.name,
                "college_or_university": "University of Camarines Norte",
                "year_graduated": 2026,
                "honors_or_awards": "",
            }
        ],
        professional_exams=[],
        trainings=[],
        curriculum_improvement_suggestions="Offer more practice interviews and employer visits.",
    )
    variant = member.tracer
    if variant == "draft":
        return {
            key: values[key]
            for key in (
                "civil_status",
                "sex",
                "region_of_origin",
                "province",
                "residence_location",
                "education",
            )
        }
    if variant in {"job_seeking", "further_study"}:
        return {
            key: values[key]
            for key in (
                "civil_status",
                "sex",
                "region_of_origin",
                "province",
                "residence_location",
                "education",
            )
        } | {
            "current_employment_state": "NEVER_EMPLOYED"
            if variant == "job_seeking"
            else "NOT_EMPLOYED",
            "unemployment_reasons": ["LACK_WORK_EXPERIENCE", "NO_JOB_OPPORTUNITY"]
            if variant == "job_seeking"
            else ["ADVANCE_STUDY"],
            "advanced_study_reasons": []
            if variant == "job_seeking"
            else ["PROFESSIONAL_DEVELOPMENT"],
            "trainings": []
            if variant == "job_seeking"
            else [
                {
                    "title": "Applied data analysis",
                    "duration_and_credits": "40 hours",
                    "institution": "Demo continuing education center",
                }
            ],
            "curriculum_improvement_suggestions": "Connect graduates with entry-level employers.",
        }
    values.update(
        present_employment_status="REGULAR_PERMANENT",
        present_occupation="Junior software support associate",
        employer_business_line="TRANSPORT_STORAGE_COMMUNICATION",
        time_to_first_job="LESS_THAN_MONTH",
        first_job_source="ADVERTISEMENT",
        useful_competencies=["INFORMATION_TECHNOLOGY", "PROBLEM_SOLVING"],
        trainings=[
            {
                "title": "Customer support and issue triage",
                "duration_and_credits": "2 days",
                "institution": "Demo employer training unit",
            }
        ],
    )
    if variant == "unrelated":
        values.update(
            present_occupation="Retail operations assistant",
            employer_business_line="WHOLESALE_RETAIL_REPAIR",
            first_job_related_to_course=False,
            curriculum_relevant_to_first_job=False,
            time_to_first_job="ONE_TO_SIX_MONTHS",
            current_job_level="RANK_CLERICAL",
            reasons_for_staying_on_job=["SALARIES_BENEFITS"],
            useful_competencies=["COMMUNICATION", "HUMAN_RELATIONS"],
        )
    if variant == "self_employed":
        values.update(
            present_employment_status="SELF_EMPLOYED",
            present_occupation="Online bookkeeping and retail business owner",
            employer_business_line="WHOLESALE_RETAIL_REPAIR",
            self_employed_college_skills="Accounting helped me price services.",
            current_job_level="SELF_EMPLOYED",
            first_job_level="SELF_EMPLOYED",
            first_job_source="FAMILY_BUSINESS",
            useful_competencies=["ENTREPRENEURIAL", "INFORMATION_TECHNOLOGY"],
            time_to_first_job="SEVEN_TO_ELEVEN_MONTHS",
        )
    return values


NO_INVENTORY_INTAKE = {
    "college_experience": "Classes are going well; I am considering a different elective track.",
    "coping_with_college_challenges": "I ask classmates for feedback and plan work a week ahead.",
    "academic_goals": "Choose electives that fit my interests without delaying graduation.",
}
CAREER_INTAKE = {
    "college_experience": "The entrepreneurship project made me interested in a small business.",
    "academic_goals": "Finish the feasibility study and prepare for internship.",
    "coping_with_college_challenges": "I divide project tasks and ask for early adviser feedback.",
}
CAREER_EVALUATION = {
    **narratives.WALK_IN_EVALUATION,
    "academic_adjustment_rating": 8,
    "financial_adjustment_rating": 5,
    "emotional_adjustment_rating": 8,
    "other_adjustment": "Career choices and project expenses need a practical plan.",
    "special_concern": "No special concern identified during this session.",
    "recommendations": "Compare internships, draft a project budget, and consult the adviser.",
}
