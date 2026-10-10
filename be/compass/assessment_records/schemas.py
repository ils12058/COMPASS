from datetime import date, datetime
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict, Field

from .services import AssessmentRecordOrdering


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class AssessmentTypeResponse(StrictSchema):
    id: UUID
    name: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssessmentTypeCreate(StrictSchema):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)


class AssessmentTypeUpdate(StrictSchema):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class AssessmentPersonReference(StrictSchema):
    id: UUID
    institutional_id: str | None
    display_name: str


class AssessmentRecordListItem(StrictSchema):
    id: UUID
    student: AssessmentPersonReference
    assessment_type: AssessmentTypeResponse
    administered_on: date
    recorded_by: AssessmentPersonReference
    created_at: datetime
    updated_at: datetime


class AssessmentRecordDetail(AssessmentRecordListItem):
    score: str
    result: str
    interpretation: str
    remarks: str


class AssessmentRecordCreate(StrictSchema):
    student_id: UUID
    assessment_type_id: UUID
    administered_on: date
    score: str = Field(default="", max_length=500)
    result: str = Field(default="", max_length=4000)
    interpretation: str = Field(default="", max_length=8000)
    remarks: str = Field(default="", max_length=4000)


class AssessmentRecordUpdate(StrictSchema):
    assessment_type_id: UUID | None = None
    administered_on: date | None = None
    score: str | None = Field(default=None, max_length=500)
    result: str | None = Field(default=None, max_length=4000)
    interpretation: str | None = Field(default=None, max_length=8000)
    remarks: str | None = Field(default=None, max_length=4000)


class AssessmentRecordPage(StrictSchema):
    items: list[AssessmentRecordListItem]
    page: int
    page_size: int
    has_next: bool
    ordering: AssessmentRecordOrdering


class AssessmentRecordFilters(StrictSchema):
    search: str | None = Field(default=None, max_length=160)
    student_id: UUID | None = None
    assessment_type_id: UUID | None = None
    administered_from: date | None = None
    administered_to: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)
    ordering: AssessmentRecordOrdering | None = None


class AssessmentStudentCollege(StrictSchema):
    id: UUID
    code: str
    name: str


class AssessmentStudentOption(AssessmentPersonReference):
    college: AssessmentStudentCollege | None


class AssessmentStudentPage(StrictSchema):
    items: list[AssessmentStudentOption]
    page: int
    page_size: int
    has_next: bool
