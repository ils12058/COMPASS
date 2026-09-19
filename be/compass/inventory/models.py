"""Explicit annual Individual Inventory persistence for the controlled F5 form."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from compass.institutional_forms.models import FormRevision
from compass.organization.models import AcademicYear, Program


class CivilStatusCategory(models.TextChoices):
    SINGLE = "SINGLE", "Single"
    MARRIED = "MARRIED", "Married"
    SOLO_PARENT = "SOLO_PARENT", "Solo Parent"
    OTHER = "OTHER", "Other"
    NOT_SPECIFIED = "NOT_SPECIFIED", "Not specified"


class CurrentReligionCategory(models.TextChoices):
    ROMAN_CATHOLIC = "ROMAN_CATHOLIC", "Roman Catholic"
    BORN_AGAIN = "BORN_AGAIN", "Born Again"
    IGLESIA_NI_CRISTO = "IGLESIA_NI_CRISTO", "Iglesia Ni Cristo"
    MORMON = "MORMON", "Mormon"
    JEHOVAHS_WITNESS = "JEHOVAHS_WITNESS", "Jehovah's Witness"
    SEVENTH_DAY_ADVENTIST = "SEVENTH_DAY_ADVENTIST", "Seventh Day Adventist"
    CHURCH_OF_CHRIST = "CHURCH_OF_CHRIST", "Church Of Christ"
    EVANGELICAL_CHRISTIAN = "EVANGELICAL_CHRISTIAN", "Evangelical Christian"
    MGCI = "MGCI", "MGCI"
    BAPTIST = "BAPTIST", "Baptist"
    PMCC = "PMCC", "PMCC"
    NONE = "NONE", "None"
    OTHER = "OTHER", "Other"
    NOT_SPECIFIED = "NOT_SPECIFIED", "Not specified"


class PWDStatus(models.TextChoices):
    PWD = "PWD", "PWD"
    NON_PWD = "NON_PWD", "Non-PWD"
    NOT_SPECIFIED = "NOT_SPECIFIED", "Not specified"


class ParentStatusCategory(models.TextChoices):
    MARRIED = "MARRIED", "Married"
    ANNULLED = "ANNULLED", "Annulled"
    LEGALLY_SEPARATED = "LEGALLY_SEPARATED", "Legally Separated"
    TEMPORARILY_SEPARATED = "TEMPORARILY_SEPARATED", "Temporarily Separated"
    PERMANENTLY_SEPARATED = "PERMANENTLY_SEPARATED", "Permanently Separated"
    LIVING_TOGETHER = "LIVING_TOGETHER", "Living Together"
    WIDOWED = "WIDOWED", "Widowed"
    MOTHER_WITH_OTHER_PARTNER = "MOTHER_WITH_OTHER_PARTNER", "Mother with other partner"
    FATHER_WITH_OTHER_PARTNER = "FATHER_WITH_OTHER_PARTNER", "Father with other partner"
    MOTHER_OFW = "MOTHER_OFW", "Mother OFW"
    FATHER_OFW = "FATHER_OFW", "Father OFW"
    OTHER = "OTHER", "Other"
    NOT_SPECIFIED = "NOT_SPECIFIED", "Not specified"


class OccupationCategory(models.TextChoices):
    GOVERNMENT_EMPLOYEE = "GOVERNMENT_EMPLOYEE", "Government Employee"
    PRIVATE_EMPLOYEE = "PRIVATE_EMPLOYEE", "Private Employee"
    LABORER = "LABORER", "Laborer"
    FARMER = "FARMER", "Farmer"
    SELF_EMPLOYED = "SELF_EMPLOYED", "Self Employed"
    OFW = "OFW", "OFW"
    NONE = "NONE", "None"
    OTHER = "OTHER", "Other"
    NOT_SPECIFIED = "NOT_SPECIFIED", "Not specified"


class AnnualIncomeStatus(models.TextChoices):
    REPORTED = "REPORTED", "Reported"
    NONE = "NONE", "None"
    NOT_SPECIFIED = "NOT_SPECIFIED", "Not specified"


class GeographicLocationKind(models.TextChoices):
    CURRENT = "CURRENT", "Current"
    PERMANENT = "PERMANENT", "Permanent"


class TransportationFrequencyCategory(models.TextChoices):
    DAILY = "DAILY", "Daily"
    SEVERAL_TIMES_A_WEEK = "SEVERAL_TIMES_A_WEEK", "Several times a week"
    WEEKLY = "WEEKLY", "Weekly"
    OCCASIONAL = "OCCASIONAL", "Occasional"
    OTHER = "OTHER", "Other"
    NOT_SPECIFIED = "NOT_SPECIFIED", "Not specified"


class Sex(models.TextChoices):
    MALE = "MALE", "Male"
    FEMALE = "FEMALE", "Female"


class FamilyMemberKind(models.TextChoices):
    FATHER = "FATHER", "Father"
    MOTHER = "MOTHER", "Mother"
    SPOUSE = "SPOUSE", "Spouse"


class ParentStatus(models.TextChoices):
    MARRIED_ANNULLED_LEGALLY_SEPARATED = (
        "MARRIED_ANNULLED_LEGALLY_SEPARATED",
        "Married / Annulled / Legally Separated",
    )
    TEMPORARILY_SEPARATED = "TEMPORARILY_SEPARATED", "Temporarily Separated"
    PERMANENTLY_SEPARATED = "PERMANENTLY_SEPARATED", "Permanently Separated"
    MOTHER_WITH_OTHER_PARTNER = "MOTHER_WITH_OTHER_PARTNER", "Mother with other partner"
    FATHER_WITH_OTHER_PARTNER = "FATHER_WITH_OTHER_PARTNER", "Father with other partner"
    WIDOW_WIDOWER_LIVING_TOGETHER = (
        "WIDOW_WIDOWER_LIVING_TOGETHER",
        "Widow / Widower / Living Together",
    )
    MOTHER_OFW = "MOTHER_OFW", "Mother OFW"
    FATHER_OFW = "FATHER_OFW", "Father OFW"


class LivingArrangement(models.TextChoices):
    OWN_HOUSE = "OWN_HOUSE", "Own House"
    BOARDING_HOUSE = "BOARDING_HOUSE", "Boarding House"
    WITH_RELATIVES = "WITH_RELATIVES", "With Relatives"


class ImmunizationType(models.TextChoices):
    CHICKEN_POX = "CHICKEN_POX", "Chicken Pox"
    BOOSTER = "BOOSTER", "Booster"
    MEASLES_MMR = "MEASLES_MMR", "Measles MMR"
    HEPATITIS_B = "HEPATITIS_B", "Hepatitis B"
    MUMPS = "MUMPS", "Mumps"
    INFLUENZA = "INFLUENZA", "Influenza"
    SMALL_POX = "SMALL_POX", "Small Pox"
    OTHER = "OTHER", "Other"


class EducationLevel(models.TextChoices):
    PREPARATORY = "PREPARATORY", "Preparatory"
    ELEMENTARY = "ELEMENTARY", "Elementary"
    JUNIOR_HIGH = "JUNIOR_HIGH", "Junior High"
    SENIOR_HIGH = "SENIOR_HIGH", "Senior High"
    TECHNICAL_VOCATIONAL = "TECHNICAL_VOCATIONAL", "Technical/Vocational Degree"
    COLLEGIATE = "COLLEGIATE", "Collegiate"


class CourseChoiceReason(models.TextChoices):
    INTEREST_APTITUDE = "INTEREST_APTITUDE", "Suited to interest and aptitude"
    MINIMAL_COST = "MINIMAL_COST", "Offered at minimal cost"
    FRIENDS = "FRIENDS", "Invited by friends"
    PARENT_CHOICE = "PARENT_CHOICE", "Parent's choice"
    JOB_OPPORTUNITIES = "JOB_OPPORTUNITIES", "Good job opportunities here and abroad"
    OTHER = "OTHER", "Other"


class InterestType(models.TextChoices):
    PAINTING = "PAINTING", "Painting"
    SINGING = "SINGING", "Singing"
    POEM_WRITING = "POEM_WRITING", "Poem Writing"
    PLAYING_INSTRUMENTS = "PLAYING_INSTRUMENTS", "Playing Instruments"
    PLANTING = "PLANTING", "Planting"
    DECLAMATION_ORATION = "DECLAMATION_ORATION", "Declamation/Oration"
    DANCING = "DANCING", "Dancing"
    COMPOSING = "COMPOSING", "Composing"
    STAGE_ACT = "STAGE_ACT", "Stage/Act"
    COOKING = "COOKING", "Cooking"


class Handedness(models.TextChoices):
    RIGHT = "RIGHT", "Right"
    LEFT = "LEFT", "Left"


class OrganizationScope(models.TextChoices):
    INSIDE_SCHOOL = "INSIDE_SCHOOL", "Inside the School"
    OUTSIDE_SCHOOL = "OUTSIDE_SCHOOL", "Outside the School"


class TransportationMode(models.TextChoices):
    TRICYCLE = "TRICYCLE", "Tricycle"
    BUS = "BUS", "Bus"
    JEEPNEY = "JEEPNEY", "Jeepney"
    VAN = "VAN", "Van"
    BOAT = "BOAT", "Boat"


class IdealAllowanceBand(models.TextChoices):
    BELOW_100 = "BELOW_100", "Php 100.00 - below"
    FROM_100_TO_499 = "FROM_100_TO_499", "Php 100.00 - 499.00"
    FROM_500_TO_1000 = "FROM_500_TO_1000", "Php 500.00 - 1,000.00"
    ABOVE_1000 = "ABOVE_1000", "Php 1,000.00 - above"


class PostGraduationField(models.TextChoices):
    PROFESSIONAL = "PROFESSIONAL", "Professional"
    AGRICULTURE = "AGRICULTURE", "Agriculture"
    BUSINESS = "BUSINESS", "Business"
    TECHNICAL = "TECHNICAL", "Technical"
    OVERSEAS_WORKER = "OVERSEAS_WORKER", "Overseas Worker"
    RELIGIOUS = "RELIGIOUS", "Religious"
    PUBLIC_SERVICE = "PUBLIC_SERVICE", "Public Service"
    OTHER = "OTHER", "Other"


class StudentInventory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="individual_inventories",
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="student_inventories",
    )
    form_revision = models.ForeignKey(
        FormRevision,
        on_delete=models.PROTECT,
        related_name="student_inventories",
    )
    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name="student_inventories",
        null=True,
        blank=True,
    )
    year_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Page 1 — personal snapshot.
    full_name_snapshot = models.CharField(max_length=200, blank=True, default="")
    nickname = models.CharField(max_length=100, blank=True, default="")
    student_number = models.CharField(max_length=64, blank=True, default="")
    date_of_birth = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=160, blank=True, default="")
    nationality = models.CharField(max_length=100, blank=True, default="")
    sex = models.CharField(max_length=16, choices=Sex.choices, blank=True, default="")
    birth_order_among_siblings = models.CharField(max_length=64, blank=True, default="")
    civil_status = models.CharField(max_length=80, blank=True, default="")
    civil_status_category = models.CharField(
        max_length=32,
        choices=CivilStatusCategory.choices,
        null=True,
        blank=True,
    )
    current_address = models.TextField(blank=True, default="")
    permanent_address = models.TextField(blank=True, default="")
    contact_number = models.CharField(max_length=64, blank=True, default="")
    email_address = models.EmailField(blank=True, default="")
    languages_spoken_at_home = models.TextField(blank=True, default="")
    languages_most_fluent = models.TextField(blank=True, default="")
    religion_from_birth = models.CharField(max_length=120, blank=True, default="")
    current_religion = models.CharField(max_length=120, blank=True, default="")
    current_religion_category = models.CharField(
        max_length=40,
        choices=CurrentReligionCategory.choices,
        null=True,
        blank=True,
    )
    parent_statuses = ArrayField(
        models.CharField(max_length=48, choices=ParentStatus.choices),
        default=list,
        blank=True,
    )
    parent_status_category = models.CharField(
        max_length=40,
        choices=ParentStatusCategory.choices,
        null=True,
        blank=True,
    )
    guardian_name = models.CharField(max_length=160, blank=True, default="")
    guardian_relationship = models.CharField(max_length=120, blank=True, default="")
    guardian_address = models.TextField(blank=True, default="")
    guardian_contact_number = models.CharField(max_length=64, blank=True, default="")
    emergency_contact_name = models.CharField(max_length=160, blank=True, default="")
    emergency_contact_number = models.CharField(max_length=64, blank=True, default="")

    # Page 2 — unique features, living, health, current study.
    friends_in_school = models.TextField(blank=True, default="")
    friends_outside_school = models.TextField(blank=True, default="")
    special_interest = models.TextField(blank=True, default="")
    special_skills_talents = models.TextField(blank=True, default="")
    hobbies_recreation = models.TextField(blank=True, default="")
    ambition_goal = models.TextField(blank=True, default="")
    characteristics = models.TextField(blank=True, default="")
    living_arrangement = models.CharField(
        max_length=32,
        choices=LivingArrangement.choices,
        blank=True,
        default="",
    )
    boarding_exclusive = models.BooleanField(null=True, blank=True)
    boarding_landlord_name = models.CharField(max_length=160, blank=True, default="")
    boarding_address = models.TextField(blank=True, default="")
    present_place_people_count = models.PositiveSmallIntegerField(null=True, blank=True)
    room_sharing_people_count = models.PositiveSmallIntegerField(null=True, blank=True)
    accidents_experienced = models.TextField(blank=True, default="")
    accidents_effect = models.TextField(blank=True, default="")
    operations_experienced = models.TextField(blank=True, default="")
    operations_effect = models.TextField(blank=True, default="")
    immunizations = ArrayField(
        models.CharField(max_length=24, choices=ImmunizationType.choices),
        default=list,
        blank=True,
    )
    immunization_other = models.CharField(max_length=160, blank=True, default="")
    height = models.CharField(max_length=64, blank=True, default="")
    weight = models.CharField(max_length=64, blank=True, default="")
    physical_disadvantage = models.TextField(blank=True, default="")
    pwd_status = models.CharField(
        max_length=32,
        choices=PWDStatus.choices,
        null=True,
        blank=True,
    )
    illness_this_year = models.TextField(blank=True, default="")
    previous_illness = models.TextField(blank=True, default="")
    course_currently_enrolled = models.CharField(max_length=180, blank=True, default="")
    major = models.CharField(max_length=180, blank=True, default="")
    schedule_satisfied = models.BooleanField(null=True, blank=True)
    schedule_satisfaction_reason = models.TextField(blank=True, default="")

    # Page 3 — course, interests, perception, prior counseling and current concerns.
    course_first_choice = models.BooleanField(null=True, blank=True)
    course_choice_reasons = ArrayField(
        models.CharField(max_length=32, choices=CourseChoiceReason.choices),
        default=list,
        blank=True,
    )
    course_choice_other = models.TextField(blank=True, default="")
    lowest_subjects_grades = models.TextField(blank=True, default="")
    highest_subjects_grades = models.TextField(blank=True, default="")
    inclination_performing_arts = models.TextField(blank=True, default="")
    inclination_sports = models.TextField(blank=True, default="")
    inclination_leadership = models.TextField(blank=True, default="")
    interests = ArrayField(
        models.CharField(max_length=32, choices=InterestType.choices),
        default=list,
        blank=True,
    )
    other_skills_hobbies = models.TextField(blank=True, default="")
    desired_extracurricular_activities = models.TextField(blank=True, default="")
    reading_preferences = models.TextField(blank=True, default="")
    handedness = models.CharField(max_length=16, choices=Handedness.choices, blank=True, default="")
    daily_hours_class = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
    )
    daily_hours_library = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
    )
    daily_hours_studying = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
    )
    daily_hours_rest = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
    )
    daily_hours_recreation = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
    )
    daily_hours_other = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
    )
    ideal_monthly_allowance = models.CharField(
        max_length=24,
        choices=IdealAllowanceBand.choices,
        blank=True,
        default="",
    )
    intended_work_field = models.CharField(
        max_length=32,
        choices=PostGraduationField.choices,
        blank=True,
        default="",
    )
    intended_work_other = models.CharField(max_length=160, blank=True, default="")
    prior_counseling_experience = models.BooleanField(null=True, blank=True)
    prior_counselor_name = models.CharField(max_length=160, blank=True, default="")
    prior_counseling_when = models.CharField(max_length=120, blank=True, default="")
    prior_counseling_where = models.CharField(max_length=200, blank=True, default="")
    current_concerns = models.TextField(blank=True, default="")
    current_fears = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        ordering = ("-academic_year__label", "student_id")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "academic_year"),
                name="inventory_student_academic_year_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(year_level__isnull=True)
                    | (models.Q(year_level__gte=1) & models.Q(year_level__lte=10))
                ),
                name="inventory_year_level_range",
            ),
        ]


class InventoryFamilyMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory = models.ForeignKey(
        StudentInventory,
        on_delete=models.CASCADE,
        related_name="family_members",
    )
    kind = models.CharField(max_length=16, choices=FamilyMemberKind.choices)
    name = models.CharField(max_length=160, blank=True, default="")
    date_of_birth = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=160, blank=True, default="")
    current_address = models.TextField(blank=True, default="")
    permanent_address = models.TextField(blank=True, default="")
    contact_number = models.CharField(max_length=64, blank=True, default="")
    email_address = models.EmailField(blank=True, default="")
    educational_attainment = models.CharField(max_length=160, blank=True, default="")
    occupation = models.CharField(max_length=160, blank=True, default="")
    occupation_category = models.CharField(
        max_length=32,
        choices=OccupationCategory.choices,
        null=True,
        blank=True,
    )
    business_address = models.TextField(blank=True, default="")
    business_telephone = models.CharField(max_length=64, blank=True, default="")
    annual_income_previous_year = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    annual_income_status = models.CharField(
        max_length=24,
        choices=AnnualIncomeStatus.choices,
        null=True,
        blank=True,
    )
    languages_spoken = models.TextField(blank=True, default="")
    religion_raised_with = models.CharField(max_length=120, blank=True, default="")
    current_religion = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        default_permissions = ()
        ordering = ("kind", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("inventory", "kind"),
                name="inventory_family_member_kind_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(annual_income_previous_year__isnull=True)
                    | models.Q(annual_income_previous_year__gte=0)
                ),
                name="inventory_family_income_nonnegative",
            ),
        ]


class InventoryGeographicLocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory = models.ForeignKey(
        StudentInventory,
        on_delete=models.CASCADE,
        related_name="geographic_locations",
    )
    kind = models.CharField(max_length=16, choices=GeographicLocationKind.choices)
    not_specified = models.BooleanField(default=False)
    region_psgc_code = models.CharField(max_length=32, blank=True, default="")
    region_name_snapshot = models.CharField(max_length=160, blank=True, default="")
    province_psgc_code = models.CharField(max_length=32, blank=True, default="")
    province_name_snapshot = models.CharField(max_length=160, blank=True, default="")
    city_municipality_psgc_code = models.CharField(max_length=32, blank=True, default="")
    city_municipality_name_snapshot = models.CharField(max_length=160, blank=True, default="")
    barangay_psgc_code = models.CharField(max_length=32, blank=True, default="")
    barangay_name_snapshot = models.CharField(max_length=160, blank=True, default="")

    class Meta:
        default_permissions = ()
        ordering = ("kind", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("inventory", "kind"),
                name="inventory_geographic_location_kind_uniq",
            ),
        ]


class InventorySibling(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory = models.ForeignKey(
        StudentInventory, on_delete=models.CASCADE, related_name="siblings"
    )
    sort_order = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=160, blank=True, default="")
    sex = models.CharField(max_length=16, choices=Sex.choices, blank=True, default="")
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    educational_attainment = models.CharField(max_length=160, blank=True, default="")
    occupation = models.CharField(max_length=160, blank=True, default="")
    is_self = models.BooleanField(default=False)

    class Meta:
        default_permissions = ()
        ordering = ("sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("inventory", "sort_order"),
                name="inventory_sibling_order_uniq",
            ),
        ]


class InventoryEducationEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory = models.ForeignKey(
        StudentInventory,
        on_delete=models.CASCADE,
        related_name="education_entries",
    )
    level = models.CharField(max_length=32, choices=EducationLevel.choices)
    school_attended_address = models.TextField(blank=True, default="")
    inclusive_years = models.CharField(max_length=100, blank=True, default="")
    awards_received = models.TextField(blank=True, default="")

    class Meta:
        default_permissions = ()
        ordering = ("level", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("inventory", "level"),
                name="inventory_education_level_uniq",
            ),
        ]


class InventoryOrganizationMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory = models.ForeignKey(
        StudentInventory,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    scope = models.CharField(max_length=24, choices=OrganizationScope.choices)
    sort_order = models.PositiveSmallIntegerField()
    organization_name = models.CharField(max_length=180, blank=True, default="")
    position_title = models.CharField(max_length=160, blank=True, default="")

    class Meta:
        default_permissions = ()
        ordering = ("scope", "sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("inventory", "scope", "sort_order"),
                name="inventory_organization_order_uniq",
            ),
        ]


class InventoryTransportationEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory = models.ForeignKey(
        StudentInventory,
        on_delete=models.CASCADE,
        related_name="transportation_entries",
    )
    mode = models.CharField(max_length=16, choices=TransportationMode.choices)
    frequency = models.CharField(max_length=100, blank=True, default="")
    frequency_category = models.CharField(
        max_length=32,
        choices=TransportationFrequencyCategory.choices,
        null=True,
        blank=True,
    )
    fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        default_permissions = ()
        ordering = ("mode", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("inventory", "mode"),
                name="inventory_transport_mode_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(fare__isnull=True) | models.Q(fare__gte=0),
                name="inventory_transport_fare_nonnegative",
            ),
        ]
