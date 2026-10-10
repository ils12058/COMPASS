# Generated for the Graduate Tracer foundation.

import django.contrib.postgres.fields
import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GraduateTracerResponse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("instrument_schema_version", models.PositiveSmallIntegerField(default=1, editable=False)),
                (
                    "status",
                    models.CharField(
                        choices=[("DRAFT", "Draft"), ("SUBMITTED", "Submitted")],
                        default="DRAFT",
                        max_length=16,
                    ),
                ),
                ("name_snapshot", models.CharField(blank=True, default="", max_length=200)),
                ("permanent_address_snapshot", models.TextField(blank=True, default="")),
                ("email_snapshot", models.EmailField(blank=True, default="", max_length=320)),
                (
                    "telephone_contact_numbers_snapshot",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                ("mobile_number_snapshot", models.CharField(blank=True, default="", max_length=64)),
                (
                    "civil_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("SINGLE", "Single"),
                            ("SEPARATED", "Separated"),
                            ("WIDOW_WIDOWER", "Widow or Widower"),
                            ("MARRIED", "Married"),
                            ("SINGLE_PARENT", "Single Parent"),
                        ],
                        default="",
                        max_length=24,
                    ),
                ),
                (
                    "sex",
                    models.CharField(
                        blank=True,
                        choices=[("MALE", "Male"), ("FEMALE", "Female")],
                        default="",
                        max_length=8,
                    ),
                ),
                ("birth_date", models.DateField(blank=True, null=True)),
                (
                    "region_of_origin",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("REGION_1", "Region 1"),
                            ("REGION_2", "Region 2"),
                            ("REGION_3", "Region 3"),
                            ("REGION_4", "Region 4"),
                            ("REGION_5", "Region 5"),
                            ("REGION_6", "Region 6"),
                            ("REGION_7", "Region 7"),
                            ("REGION_8", "Region 8"),
                            ("REGION_9", "Region 9"),
                            ("REGION_10", "Region 10"),
                            ("REGION_11", "Region 11"),
                            ("REGION_12", "Region 12"),
                            ("NCR", "NCR"),
                            ("CAR", "CAR"),
                            ("ARMM", "ARMM"),
                            ("CARAGA", "CARAGA"),
                        ],
                        default="",
                        max_length=16,
                    ),
                ),
                ("province", models.CharField(blank=True, default="", max_length=160)),
                (
                    "residence_location",
                    models.CharField(
                        blank=True,
                        choices=[("CITY", "City"), ("MUNICIPALITY", "Municipality")],
                        default="",
                        max_length=16,
                    ),
                ),
                (
                    "undergraduate_degree_reasons",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                (
                                    "HIGH_GRADES_RELATED_COURSE",
                                    "High grades in the course or subject area(s) related to the course",
                                ),
                                ("GOOD_GRADES_HIGH_SCHOOL", "Good grades in high school"),
                                ("PARENTS_RELATIVES", "Influence of parents or relatives"),
                                ("PEER_INFLUENCE", "Peer Influence"),
                                ("ROLE_MODEL", "Inspired by a role model"),
                                ("PASSION_PROFESSION", "Strong passion for the profession"),
                                ("IMMEDIATE_EMPLOYMENT", "Prospect for immediate employment"),
                                ("STATUS_PRESTIGE", "Status or prestige of the profession"),
                                (
                                    "COURSE_AVAILABILITY",
                                    "Availability of course offering in chosen institution",
                                ),
                                ("CAREER_ADVANCEMENT", "Prospect of career advancement"),
                                ("AFFORDABLE", "Affordable for the family"),
                                (
                                    "ATTRACTIVE_COMPENSATION",
                                    "Prospect of attractive compensation",
                                ),
                                ("EMPLOYMENT_ABROAD", "Opportunity for employment abroad"),
                                (
                                    "NO_PARTICULAR_CHOICE",
                                    "No particular choice or no better idea",
                                ),
                            ],
                            max_length=48,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                (
                    "graduate_study_reasons",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                (
                                    "HIGH_GRADES_RELATED_COURSE",
                                    "High grades in the course or subject area(s) related to the course",
                                ),
                                ("GOOD_GRADES_HIGH_SCHOOL", "Good grades in high school"),
                                ("PARENTS_RELATIVES", "Influence of parents or relatives"),
                                ("PEER_INFLUENCE", "Peer Influence"),
                                ("ROLE_MODEL", "Inspired by a role model"),
                                ("PASSION_PROFESSION", "Strong passion for the profession"),
                                ("IMMEDIATE_EMPLOYMENT", "Prospect for immediate employment"),
                                ("STATUS_PRESTIGE", "Status or prestige of the profession"),
                                (
                                    "COURSE_AVAILABILITY",
                                    "Availability of course offering in chosen institution",
                                ),
                                ("CAREER_ADVANCEMENT", "Prospect of career advancement"),
                                ("AFFORDABLE", "Affordable for the family"),
                                (
                                    "ATTRACTIVE_COMPENSATION",
                                    "Prospect of attractive compensation",
                                ),
                                ("EMPLOYMENT_ABROAD", "Opportunity for employment abroad"),
                                (
                                    "NO_PARTICULAR_CHOICE",
                                    "No particular choice or no better idea",
                                ),
                            ],
                            max_length=48,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("degree_other_reason", models.TextField(blank=True, default="")),
                (
                    "advanced_study_reasons",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("PROMOTION", "For promotion"),
                                ("PROFESSIONAL_DEVELOPMENT", "For professional development"),
                                ("OTHER", "Others"),
                            ],
                            max_length=40,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("advanced_study_other_reason", models.TextField(blank=True, default="")),
                (
                    "current_employment_state",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("EMPLOYED", "Yes"),
                            ("NOT_EMPLOYED", "No"),
                            ("NEVER_EMPLOYED", "Never Employed"),
                        ],
                        default="",
                        max_length=24,
                    ),
                ),
                (
                    "unemployment_reasons",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("ADVANCE_STUDY", "Advance or further study"),
                                (
                                    "FAMILY_CONCERN",
                                    "Family concern and decided not to find a job",
                                ),
                                ("HEALTH_RELATED", "Health-related reason(s)"),
                                ("LACK_WORK_EXPERIENCE", "Lack of work experience"),
                                ("NO_JOB_OPPORTUNITY", "No job opportunity"),
                                ("DID_NOT_LOOK", "Did not look for a job"),
                                ("OTHER", "Other reason(s)"),
                            ],
                            max_length=40,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("unemployment_other_reason", models.TextField(blank=True, default="")),
                (
                    "present_employment_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("REGULAR_PERMANENT", "Regular or Permanent"),
                            ("TEMPORARY", "Temporary"),
                            ("CASUAL", "Casual"),
                            ("CONTRACTUAL", "Contractual"),
                            ("SELF_EMPLOYED", "Self-employed"),
                        ],
                        default="",
                        max_length=32,
                    ),
                ),
                ("self_employed_college_skills", models.TextField(blank=True, default="")),
                ("present_occupation", models.CharField(blank=True, default="", max_length=255)),
                (
                    "employer_business_line",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("AGRICULTURE_HUNTING_FORESTRY", "Agriculture, Hunting and Forestry"),
                            ("FISHING", "Fishing"),
                            ("MINING_QUARRYING", "Mining and Quarrying"),
                            ("MANUFACTURING", "Manufacturing"),
                            ("ELECTRICITY_GAS_WATER", "Electricity, Gas and Water Supply"),
                            ("CONSTRUCTION", "Construction"),
                            (
                                "WHOLESALE_RETAIL_REPAIR",
                                "Wholesale and Retail Trade, repair of motor vehicles, motorcycles and personal and household goods",
                            ),
                            ("HOTELS_RESTAURANTS", "Hotels and Restaurants"),
                            (
                                "TRANSPORT_STORAGE_COMMUNICATION",
                                "Transport Storage and Communication",
                            ),
                            ("FINANCIAL_INTERMEDIATION", "Financial Intermediation"),
                            (
                                "REAL_ESTATE_RENTING_BUSINESS",
                                "Real Estate, Renting and Business Activities",
                            ),
                            (
                                "PUBLIC_ADMIN_DEFENSE_SOCIAL_SECURITY",
                                "Public Administration and Defense; Compulsory Social Security",
                            ),
                            ("EDUCATION", "Education"),
                            ("HEALTH_SOCIAL_WORK", "Health and Social Work"),
                            (
                                "OTHER_COMMUNITY_SOCIAL_PERSONAL",
                                "Other Community, Social and Personal Service Activities",
                            ),
                            (
                                "PRIVATE_HOUSEHOLDS_EMPLOYED_PERSONS",
                                "Private Households with Employed Persons",
                            ),
                            (
                                "EXTRA_TERRITORIAL_ORGANIZATIONS",
                                "Extra-territorial Organizations and Bodies",
                            ),
                        ],
                        default="",
                        max_length=48,
                    ),
                ),
                (
                    "place_of_work",
                    models.CharField(
                        blank=True,
                        choices=[("LOCAL", "Local"), ("ABROAD", "Abroad")],
                        default="",
                        max_length=16,
                    ),
                ),
                ("first_job_after_college", models.BooleanField(blank=True, null=True)),
                (
                    "reasons_for_staying_on_job",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("SALARIES_BENEFITS", "Salaries and benefits"),
                                ("CAREER_CHALLENGE", "Career challenge"),
                                ("RELATED_SPECIAL_SKILL", "Related to special skill"),
                                ("RELATED_COURSE", "Related to course or program of study"),
                                ("PROXIMITY_RESIDENCE", "Proximity to residence"),
                                ("PEER_INFLUENCE", "Peer influence"),
                                ("FAMILY_INFLUENCE", "Family influence"),
                                ("OTHER", "Other reason(s)"),
                            ],
                            max_length=40,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("reasons_for_staying_other", models.TextField(blank=True, default="")),
                ("first_job_related_to_course", models.BooleanField(blank=True, null=True)),
                (
                    "reasons_for_accepting_first_job",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("SALARIES_BENEFITS", "Salaries & benefits"),
                                ("CAREER_CHALLENGE", "Career challenge"),
                                ("RELATED_SPECIAL_SKILLS", "Related to special skills"),
                                ("PROXIMITY_RESIDENCE", "Proximity to residence"),
                                ("OTHER", "Other"),
                            ],
                            max_length=40,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("reasons_for_accepting_other", models.TextField(blank=True, default="")),
                (
                    "reasons_for_changing_job",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("SALARIES_BENEFITS", "Salaries & benefits"),
                                ("CAREER_CHALLENGE", "Career challenge"),
                                ("RELATED_SPECIAL_SKILLS", "Related to special skills"),
                                ("PROXIMITY_RESIDENCE", "Proximity to residence"),
                                ("OTHER", "Other"),
                            ],
                            max_length=40,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("reasons_for_changing_other", models.TextField(blank=True, default="")),
                (
                    "first_job_duration",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("LESS_THAN_MONTH", "Less than a month"),
                            ("ONE_TO_SIX_MONTHS", "1 to 6 months"),
                            ("SEVEN_TO_ELEVEN_MONTHS", "7 to 11 months"),
                            ("ONE_TO_LT_TWO_YEARS", "1 year to less than 2 years"),
                            ("TWO_TO_LT_THREE_YEARS", "2 years to less than 3 years"),
                            ("THREE_TO_LT_FOUR_YEARS", "3 years to less than 4 years"),
                            ("OTHER", "Others"),
                        ],
                        default="",
                        max_length=32,
                    ),
                ),
                ("first_job_duration_other", models.TextField(blank=True, default="")),
                (
                    "first_job_source",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("ADVERTISEMENT", "Response to an advertisement"),
                            ("WALK_IN", "As walk-in applicant"),
                            ("RECOMMENDED", "Recommended by someone"),
                            ("FRIENDS", "Information from friends"),
                            ("SCHOOL_PLACEMENT", "Arranged by school's job placement officer"),
                            ("FAMILY_BUSINESS", "Family business"),
                            (
                                "JOB_FAIR_PESO",
                                "Job Fair or Public Employment Service Office (PESO)",
                            ),
                            ("OTHER", "Others"),
                        ],
                        default="",
                        max_length=32,
                    ),
                ),
                ("first_job_source_other", models.TextField(blank=True, default="")),
                (
                    "time_to_first_job",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("LESS_THAN_MONTH", "Less than a month"),
                            ("ONE_TO_SIX_MONTHS", "1 to 6 months"),
                            ("SEVEN_TO_ELEVEN_MONTHS", "7 to 11 months"),
                            ("ONE_TO_LT_TWO_YEARS", "1 year to less than 2 years"),
                            ("TWO_TO_LT_THREE_YEARS", "2 years to less than 3 years"),
                            ("THREE_TO_LT_FOUR_YEARS", "3 years to less than 4 years"),
                            ("OTHER", "Others"),
                        ],
                        default="",
                        max_length=32,
                    ),
                ),
                ("time_to_first_job_other", models.TextField(blank=True, default="")),
                (
                    "first_job_level",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("RANK_CLERICAL", "Rank or Clerical"),
                            (
                                "PROFESSIONAL_TECHNICAL_SUPERVISORY",
                                "Professional, Technical or Supervisory",
                            ),
                            ("MANAGERIAL_EXECUTIVE", "Managerial or Executive"),
                            ("SELF_EMPLOYED", "Self-employed"),
                        ],
                        default="",
                        max_length=48,
                    ),
                ),
                (
                    "current_job_level",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("RANK_CLERICAL", "Rank or Clerical"),
                            (
                                "PROFESSIONAL_TECHNICAL_SUPERVISORY",
                                "Professional, Technical or Supervisory",
                            ),
                            ("MANAGERIAL_EXECUTIVE", "Managerial or Executive"),
                            ("SELF_EMPLOYED", "Self-employed"),
                        ],
                        default="",
                        max_length=48,
                    ),
                ),
                (
                    "initial_gross_monthly_earning",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("BELOW_5000", "Below P5,000.00"),
                            (
                                "FROM_5000_TO_LT_10000",
                                "P5,000.00 to less than P10,000.00",
                            ),
                            (
                                "FROM_10000_TO_LT_15000",
                                "P10,000.00 to less than P15,000.00",
                            ),
                            (
                                "FROM_15000_TO_LT_20000",
                                "P15,000.00 to less than P20,000.00",
                            ),
                            (
                                "FROM_20000_TO_LT_25000",
                                "P20,000.00 to less than P25,000.00",
                            ),
                            ("FROM_25000_UP", "P25,000.00 and above"),
                        ],
                        default="",
                        max_length=32,
                    ),
                ),
                ("curriculum_relevant_to_first_job", models.BooleanField(blank=True, null=True)),
                (
                    "useful_competencies",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ("COMMUNICATION", "Communication skills"),
                                ("HUMAN_RELATIONS", "Human Relations skills"),
                                ("ENTREPRENEURIAL", "Entrepreneurial skills"),
                                (
                                    "INFORMATION_TECHNOLOGY",
                                    "Information Technology skills",
                                ),
                                ("PROBLEM_SOLVING", "Problem-solving skills"),
                                ("CRITICAL_THINKING", "Critical Thinking skills"),
                                ("OTHER", "Other skills"),
                            ],
                            max_length=40,
                        ),
                        blank=True,
                        default=list,
                        size=None,
                    ),
                ),
                ("useful_competencies_other", models.TextField(blank=True, default="")),
                ("curriculum_improvement_suggestions", models.TextField(blank=True, default="")),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="graduate_tracer_responses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="GraduateTracerEducation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "position",
                    models.PositiveSmallIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                ("degree_and_specialization", models.CharField(max_length=255)),
                ("college_or_university", models.CharField(max_length=255)),
                (
                    "year_graduated",
                    models.PositiveSmallIntegerField(
                        validators=[django.core.validators.MinValueValidator(1900)]
                    ),
                ),
                ("honors_or_awards", models.CharField(blank=True, default="", max_length=255)),
                (
                    "response",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="education_rows",
                        to="graduate_tracer.graduatetracerresponse",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="GraduateTracerProfessionalExam",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "position",
                    models.PositiveSmallIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                ("examination_name", models.CharField(max_length=255)),
                ("date_taken", models.DateField(blank=True, null=True)),
                ("rating", models.CharField(blank=True, default="", max_length=128)),
                (
                    "response",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="professional_exam_rows",
                        to="graduate_tracer.graduatetracerresponse",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="GraduateTracerTraining",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "position",
                    models.PositiveSmallIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("duration_and_credits", models.CharField(blank=True, default="", max_length=255)),
                ("institution", models.CharField(blank=True, default="", max_length=255)),
                (
                    "response",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="training_rows",
                        to="graduate_tracer.graduatetracerresponse",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="graduatetracerresponse",
            constraint=models.UniqueConstraint(
                fields=("student", "instrument_schema_version"),
                name="graduate_tracer_student_schema_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="graduatetracerresponse",
            constraint=models.CheckConstraint(
                condition=models.Q(("instrument_schema_version", 1)),
                name="graduate_tracer_schema_version_one",
            ),
        ),
        migrations.AddConstraint(
            model_name="graduatetracerresponse",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ["DRAFT", "SUBMITTED"])),
                name="graduate_tracer_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="graduatetracerresponse",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("status", "DRAFT"), ("submitted_at__isnull", True))
                    | models.Q(("status", "SUBMITTED"), ("submitted_at__isnull", False))
                ),
                name="graduate_tracer_submission_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="graduatetracereducation",
            constraint=models.UniqueConstraint(
                fields=("response", "position"),
                name="graduate_tracer_education_position_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="graduatetracerprofessionalexam",
            constraint=models.UniqueConstraint(
                fields=("response", "position"),
                name="graduate_tracer_exam_position_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="graduatetracertraining",
            constraint=models.UniqueConstraint(
                fields=("response", "position"),
                name="graduate_tracer_training_position_uniq",
            ),
        ),
    ]
