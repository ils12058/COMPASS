"""Source-faithful persistence for the supplied CHED Graduate Tracer Survey."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator
from django.db import models

GTS_SCHEMA_VERSION = 1


class GraduateTracerStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"


class GTSCivilStatus(models.TextChoices):
    SINGLE = "SINGLE", "Single"
    SEPARATED = "SEPARATED", "Separated"
    WIDOW_WIDOWER = "WIDOW_WIDOWER", "Widow or Widower"
    MARRIED = "MARRIED", "Married"
    SINGLE_PARENT = "SINGLE_PARENT", "Single Parent"


class GTSSex(models.TextChoices):
    MALE = "MALE", "Male"
    FEMALE = "FEMALE", "Female"


class GTSRegionOfOrigin(models.TextChoices):
    REGION_1 = "REGION_1", "Region 1"
    REGION_2 = "REGION_2", "Region 2"
    REGION_3 = "REGION_3", "Region 3"
    REGION_4 = "REGION_4", "Region 4"
    REGION_5 = "REGION_5", "Region 5"
    REGION_6 = "REGION_6", "Region 6"
    REGION_7 = "REGION_7", "Region 7"
    REGION_8 = "REGION_8", "Region 8"
    REGION_9 = "REGION_9", "Region 9"
    REGION_10 = "REGION_10", "Region 10"
    REGION_11 = "REGION_11", "Region 11"
    REGION_12 = "REGION_12", "Region 12"
    NCR = "NCR", "NCR"
    CAR = "CAR", "CAR"
    ARMM = "ARMM", "ARMM"
    CARAGA = "CARAGA", "CARAGA"


class GTSResidenceLocation(models.TextChoices):
    CITY = "CITY", "City"
    MUNICIPALITY = "MUNICIPALITY", "Municipality"


class GTSDegreeReason(models.TextChoices):
    HIGH_GRADES_RELATED_COURSE = (
        "HIGH_GRADES_RELATED_COURSE",
        "High grades in the course or subject area(s) related to the course",
    )
    GOOD_GRADES_HIGH_SCHOOL = "GOOD_GRADES_HIGH_SCHOOL", "Good grades in high school"
    PARENTS_RELATIVES = "PARENTS_RELATIVES", "Influence of parents or relatives"
    PEER_INFLUENCE = "PEER_INFLUENCE", "Peer Influence"
    ROLE_MODEL = "ROLE_MODEL", "Inspired by a role model"
    PASSION_PROFESSION = "PASSION_PROFESSION", "Strong passion for the profession"
    IMMEDIATE_EMPLOYMENT = "IMMEDIATE_EMPLOYMENT", "Prospect for immediate employment"
    STATUS_PRESTIGE = "STATUS_PRESTIGE", "Status or prestige of the profession"
    COURSE_AVAILABILITY = (
        "COURSE_AVAILABILITY",
        "Availability of course offering in chosen institution",
    )
    CAREER_ADVANCEMENT = "CAREER_ADVANCEMENT", "Prospect of career advancement"
    AFFORDABLE = "AFFORDABLE", "Affordable for the family"
    ATTRACTIVE_COMPENSATION = "ATTRACTIVE_COMPENSATION", "Prospect of attractive compensation"
    EMPLOYMENT_ABROAD = "EMPLOYMENT_ABROAD", "Opportunity for employment abroad"
    NO_PARTICULAR_CHOICE = "NO_PARTICULAR_CHOICE", "No particular choice or no better idea"


class GTSAdvancedStudyReason(models.TextChoices):
    PROMOTION = "PROMOTION", "For promotion"
    PROFESSIONAL_DEVELOPMENT = "PROFESSIONAL_DEVELOPMENT", "For professional development"
    OTHER = "OTHER", "Others"


class GTSEmploymentState(models.TextChoices):
    EMPLOYED = "EMPLOYED", "Yes"
    NOT_EMPLOYED = "NOT_EMPLOYED", "No"
    NEVER_EMPLOYED = "NEVER_EMPLOYED", "Never Employed"


class GTSUnemploymentReason(models.TextChoices):
    ADVANCE_STUDY = "ADVANCE_STUDY", "Advance or further study"
    FAMILY_CONCERN = "FAMILY_CONCERN", "Family concern and decided not to find a job"
    HEALTH_RELATED = "HEALTH_RELATED", "Health-related reason(s)"
    LACK_WORK_EXPERIENCE = "LACK_WORK_EXPERIENCE", "Lack of work experience"
    NO_JOB_OPPORTUNITY = "NO_JOB_OPPORTUNITY", "No job opportunity"
    DID_NOT_LOOK = "DID_NOT_LOOK", "Did not look for a job"
    OTHER = "OTHER", "Other reason(s)"


class GTSPresentEmploymentStatus(models.TextChoices):
    REGULAR_PERMANENT = "REGULAR_PERMANENT", "Regular or Permanent"
    TEMPORARY = "TEMPORARY", "Temporary"
    CASUAL = "CASUAL", "Casual"
    CONTRACTUAL = "CONTRACTUAL", "Contractual"
    SELF_EMPLOYED = "SELF_EMPLOYED", "Self-employed"


class GTSBusinessLine(models.TextChoices):
    AGRICULTURE_HUNTING_FORESTRY = (
        "AGRICULTURE_HUNTING_FORESTRY",
        "Agriculture, Hunting and Forestry",
    )
    FISHING = "FISHING", "Fishing"
    MINING_QUARRYING = "MINING_QUARRYING", "Mining and Quarrying"
    MANUFACTURING = "MANUFACTURING", "Manufacturing"
    ELECTRICITY_GAS_WATER = "ELECTRICITY_GAS_WATER", "Electricity, Gas and Water Supply"
    CONSTRUCTION = "CONSTRUCTION", "Construction"
    WHOLESALE_RETAIL_REPAIR = (
        "WHOLESALE_RETAIL_REPAIR",
        "Wholesale and Retail Trade, repair of motor vehicles, motorcycles and "
        "personal and household goods",
    )
    HOTELS_RESTAURANTS = "HOTELS_RESTAURANTS", "Hotels and Restaurants"
    TRANSPORT_STORAGE_COMMUNICATION = (
        "TRANSPORT_STORAGE_COMMUNICATION",
        "Transport Storage and Communication",
    )
    FINANCIAL_INTERMEDIATION = "FINANCIAL_INTERMEDIATION", "Financial Intermediation"
    REAL_ESTATE_RENTING_BUSINESS = (
        "REAL_ESTATE_RENTING_BUSINESS",
        "Real Estate, Renting and Business Activities",
    )
    PUBLIC_ADMIN_DEFENSE_SOCIAL_SECURITY = (
        "PUBLIC_ADMIN_DEFENSE_SOCIAL_SECURITY",
        "Public Administration and Defense; Compulsory Social Security",
    )
    EDUCATION = "EDUCATION", "Education"
    HEALTH_SOCIAL_WORK = "HEALTH_SOCIAL_WORK", "Health and Social Work"
    OTHER_COMMUNITY_SOCIAL_PERSONAL = (
        "OTHER_COMMUNITY_SOCIAL_PERSONAL",
        "Other Community, Social and Personal Service Activities",
    )
    PRIVATE_HOUSEHOLDS_EMPLOYED_PERSONS = (
        "PRIVATE_HOUSEHOLDS_EMPLOYED_PERSONS",
        "Private Households with Employed Persons",
    )
    EXTRA_TERRITORIAL_ORGANIZATIONS = (
        "EXTRA_TERRITORIAL_ORGANIZATIONS",
        "Extra-territorial Organizations and Bodies",
    )


class GTSPlaceOfWork(models.TextChoices):
    LOCAL = "LOCAL", "Local"
    ABROAD = "ABROAD", "Abroad"


class GTSStayingReason(models.TextChoices):
    SALARIES_BENEFITS = "SALARIES_BENEFITS", "Salaries and benefits"
    CAREER_CHALLENGE = "CAREER_CHALLENGE", "Career challenge"
    RELATED_SPECIAL_SKILL = "RELATED_SPECIAL_SKILL", "Related to special skill"
    RELATED_COURSE = "RELATED_COURSE", "Related to course or program of study"
    PROXIMITY_RESIDENCE = "PROXIMITY_RESIDENCE", "Proximity to residence"
    PEER_INFLUENCE = "PEER_INFLUENCE", "Peer influence"
    FAMILY_INFLUENCE = "FAMILY_INFLUENCE", "Family influence"
    OTHER = "OTHER", "Other reason(s)"


class GTSJobReason(models.TextChoices):
    SALARIES_BENEFITS = "SALARIES_BENEFITS", "Salaries & benefits"
    CAREER_CHALLENGE = "CAREER_CHALLENGE", "Career challenge"
    RELATED_SPECIAL_SKILLS = "RELATED_SPECIAL_SKILLS", "Related to special skills"
    PROXIMITY_RESIDENCE = "PROXIMITY_RESIDENCE", "Proximity to residence"
    OTHER = "OTHER", "Other"


class GTSFirstJobDuration(models.TextChoices):
    LESS_THAN_MONTH = "LESS_THAN_MONTH", "Less than a month"
    ONE_TO_SIX_MONTHS = "ONE_TO_SIX_MONTHS", "1 to 6 months"
    SEVEN_TO_ELEVEN_MONTHS = "SEVEN_TO_ELEVEN_MONTHS", "7 to 11 months"
    ONE_TO_LT_TWO_YEARS = "ONE_TO_LT_TWO_YEARS", "1 year to less than 2 years"
    TWO_TO_LT_THREE_YEARS = "TWO_TO_LT_THREE_YEARS", "2 years to less than 3 years"
    THREE_TO_LT_FOUR_YEARS = "THREE_TO_LT_FOUR_YEARS", "3 years to less than 4 years"
    OTHER = "OTHER", "Others"


class GTSFirstJobSource(models.TextChoices):
    ADVERTISEMENT = "ADVERTISEMENT", "Response to an advertisement"
    WALK_IN = "WALK_IN", "As walk-in applicant"
    RECOMMENDED = "RECOMMENDED", "Recommended by someone"
    FRIENDS = "FRIENDS", "Information from friends"
    SCHOOL_PLACEMENT = "SCHOOL_PLACEMENT", "Arranged by school's job placement officer"
    FAMILY_BUSINESS = "FAMILY_BUSINESS", "Family business"
    JOB_FAIR_PESO = "JOB_FAIR_PESO", "Job Fair or Public Employment Service Office (PESO)"
    OTHER = "OTHER", "Others"


class GTSJobLevel(models.TextChoices):
    RANK_CLERICAL = "RANK_CLERICAL", "Rank or Clerical"
    PROFESSIONAL_TECHNICAL_SUPERVISORY = (
        "PROFESSIONAL_TECHNICAL_SUPERVISORY",
        "Professional, Technical or Supervisory",
    )
    MANAGERIAL_EXECUTIVE = "MANAGERIAL_EXECUTIVE", "Managerial or Executive"
    SELF_EMPLOYED = "SELF_EMPLOYED", "Self-employed"


class GTSEarningBracket(models.TextChoices):
    BELOW_5000 = "BELOW_5000", "Below P5,000.00"
    FROM_5000_TO_LT_10000 = "FROM_5000_TO_LT_10000", "P5,000.00 to less than P10,000.00"
    FROM_10000_TO_LT_15000 = (
        "FROM_10000_TO_LT_15000",
        "P10,000.00 to less than P15,000.00",
    )
    FROM_15000_TO_LT_20000 = (
        "FROM_15000_TO_LT_20000",
        "P15,000.00 to less than P20,000.00",
    )
    FROM_20000_TO_LT_25000 = (
        "FROM_20000_TO_LT_25000",
        "P20,000.00 to less than P25,000.00",
    )
    FROM_25000_UP = "FROM_25000_UP", "P25,000.00 and above"


class GTSUsefulCompetency(models.TextChoices):
    COMMUNICATION = "COMMUNICATION", "Communication skills"
    HUMAN_RELATIONS = "HUMAN_RELATIONS", "Human Relations skills"
    ENTREPRENEURIAL = "ENTREPRENEURIAL", "Entrepreneurial skills"
    INFORMATION_TECHNOLOGY = "INFORMATION_TECHNOLOGY", "Information Technology skills"
    PROBLEM_SOLVING = "PROBLEM_SOLVING", "Problem-solving skills"
    CRITICAL_THINKING = "CRITICAL_THINKING", "Critical Thinking skills"
    OTHER = "OTHER", "Other skills"


class GraduateTracerResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="graduate_tracer_responses",
    )
    instrument_schema_version = models.PositiveSmallIntegerField(
        default=GTS_SCHEMA_VERSION, editable=False
    )
    status = models.CharField(
        max_length=16,
        choices=GraduateTracerStatus.choices,
        default=GraduateTracerStatus.DRAFT,
    )

    name_snapshot = models.CharField(max_length=200, blank=True, default="")
    permanent_address_snapshot = models.TextField(blank=True, default="")
    email_snapshot = models.EmailField(max_length=320, blank=True, default="")
    telephone_contact_numbers_snapshot = models.CharField(max_length=128, blank=True, default="")
    mobile_number_snapshot = models.CharField(max_length=64, blank=True, default="")
    civil_status = models.CharField(
        max_length=24, choices=GTSCivilStatus.choices, blank=True, default=""
    )
    sex = models.CharField(max_length=8, choices=GTSSex.choices, blank=True, default="")
    birth_date = models.DateField(null=True, blank=True)
    region_of_origin = models.CharField(
        max_length=16,
        choices=GTSRegionOfOrigin.choices,
        blank=True,
        default="",
    )
    province = models.CharField(max_length=160, blank=True, default="")
    residence_location = models.CharField(
        max_length=16,
        choices=GTSResidenceLocation.choices,
        blank=True,
        default="",
    )

    undergraduate_degree_reasons = ArrayField(
        models.CharField(max_length=48, choices=GTSDegreeReason.choices),
        default=list,
        blank=True,
    )
    graduate_study_reasons = ArrayField(
        models.CharField(max_length=48, choices=GTSDegreeReason.choices),
        default=list,
        blank=True,
    )
    degree_other_reason = models.TextField(blank=True, default="")

    advanced_study_reasons = ArrayField(
        models.CharField(max_length=40, choices=GTSAdvancedStudyReason.choices),
        default=list,
        blank=True,
    )
    advanced_study_other_reason = models.TextField(blank=True, default="")

    current_employment_state = models.CharField(
        max_length=24,
        choices=GTSEmploymentState.choices,
        blank=True,
        default="",
    )
    unemployment_reasons = ArrayField(
        models.CharField(max_length=40, choices=GTSUnemploymentReason.choices),
        default=list,
        blank=True,
    )
    unemployment_other_reason = models.TextField(blank=True, default="")

    present_employment_status = models.CharField(
        max_length=32,
        choices=GTSPresentEmploymentStatus.choices,
        blank=True,
        default="",
    )
    self_employed_college_skills = models.TextField(blank=True, default="")
    present_occupation = models.CharField(max_length=255, blank=True, default="")
    employer_business_line = models.CharField(
        max_length=48,
        choices=GTSBusinessLine.choices,
        blank=True,
        default="",
    )
    place_of_work = models.CharField(
        max_length=16, choices=GTSPlaceOfWork.choices, blank=True, default=""
    )
    first_job_after_college = models.BooleanField(null=True, blank=True)

    reasons_for_staying_on_job = ArrayField(
        models.CharField(max_length=40, choices=GTSStayingReason.choices),
        default=list,
        blank=True,
    )
    reasons_for_staying_other = models.TextField(blank=True, default="")
    first_job_related_to_course = models.BooleanField(null=True, blank=True)

    reasons_for_accepting_first_job = ArrayField(
        models.CharField(max_length=40, choices=GTSJobReason.choices),
        default=list,
        blank=True,
    )
    reasons_for_accepting_other = models.TextField(blank=True, default="")
    reasons_for_changing_job = ArrayField(
        models.CharField(max_length=40, choices=GTSJobReason.choices),
        default=list,
        blank=True,
    )
    reasons_for_changing_other = models.TextField(blank=True, default="")

    first_job_duration = models.CharField(
        max_length=32,
        choices=GTSFirstJobDuration.choices,
        blank=True,
        default="",
    )
    first_job_duration_other = models.TextField(blank=True, default="")
    first_job_source = models.CharField(
        max_length=32,
        choices=GTSFirstJobSource.choices,
        blank=True,
        default="",
    )
    first_job_source_other = models.TextField(blank=True, default="")
    time_to_first_job = models.CharField(
        max_length=32,
        choices=GTSFirstJobDuration.choices,
        blank=True,
        default="",
    )
    time_to_first_job_other = models.TextField(blank=True, default="")
    first_job_level = models.CharField(
        max_length=48,
        choices=GTSJobLevel.choices,
        blank=True,
        default="",
    )
    current_job_level = models.CharField(
        max_length=48,
        choices=GTSJobLevel.choices,
        blank=True,
        default="",
    )
    initial_gross_monthly_earning = models.CharField(
        max_length=32,
        choices=GTSEarningBracket.choices,
        blank=True,
        default="",
    )
    curriculum_relevant_to_first_job = models.BooleanField(null=True, blank=True)
    useful_competencies = ArrayField(
        models.CharField(max_length=40, choices=GTSUsefulCompetency.choices),
        default=list,
        blank=True,
    )
    useful_competencies_other = models.TextField(blank=True, default="")
    curriculum_improvement_suggestions = models.TextField(blank=True, default="")

    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "instrument_schema_version"),
                name="graduate_tracer_student_schema_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(instrument_schema_version=GTS_SCHEMA_VERSION),
                name="graduate_tracer_schema_version_one",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=GraduateTracerStatus.values),
                name="graduate_tracer_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status=GraduateTracerStatus.DRAFT, submitted_at__isnull=True)
                    | models.Q(status=GraduateTracerStatus.SUBMITTED, submitted_at__isnull=False)
                ),
                name="graduate_tracer_submission_shape",
            ),
        ]


class GraduateTracerEducation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    response = models.ForeignKey(
        GraduateTracerResponse,
        on_delete=models.CASCADE,
        related_name="education_rows",
    )
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    degree_and_specialization = models.CharField(max_length=255)
    college_or_university = models.CharField(max_length=255)
    year_graduated = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])
    honors_or_awards = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        default_permissions = ()
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("response", "position"),
                name="graduate_tracer_education_position_uniq",
            )
        ]


class GraduateTracerProfessionalExam(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    response = models.ForeignKey(
        GraduateTracerResponse,
        on_delete=models.CASCADE,
        related_name="professional_exam_rows",
    )
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    examination_name = models.CharField(max_length=255)
    date_taken = models.DateField(null=True, blank=True)
    rating = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        default_permissions = ()
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("response", "position"),
                name="graduate_tracer_exam_position_uniq",
            )
        ]


class GraduateTracerTraining(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    response = models.ForeignKey(
        GraduateTracerResponse,
        on_delete=models.CASCADE,
        related_name="training_rows",
    )
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    title = models.CharField(max_length=255)
    duration_and_credits = models.CharField(max_length=255, blank=True, default="")
    institution = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        default_permissions = ()
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("response", "position"),
                name="graduate_tracer_training_position_uniq",
            )
        ]
