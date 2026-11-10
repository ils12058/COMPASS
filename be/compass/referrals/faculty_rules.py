"""Faculty Referral eligibility, confirmation limits and disclosure boundaries."""

from compass.accounts.models import User
from compass.organization.models import College, FacultyAffiliation
from compass.referrals.errors import ReferralError

CONFIRMATION_MAX_AGE = 300
LOOKUP_ACTOR_LIMIT = 10
LOOKUP_IP_LIMIT = 30
LOOKUP_WINDOW = 300
DIGITAL_FORM = ("UCN-OP-GCO-01F3", "1", 1)
ADMINISTRATIVE_ROLES = frozenset({"COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"})


class FacultyReferralError(ReferralError):
    def __init__(self, code, status=403):
        self.code = "faculty_referral_" + code
        self.status = status
        super().__init__("The Faculty Referral operation is unavailable.")


class AdministrativeReferralError(ReferralError):
    def __init__(self, code, status=403):
        self.code = "referral_administration_" + code
        self.status = status
        super().__init__("The Referral administrative operation is unavailable.")


def active_colleges():
    return College.objects.filter(is_active=True, campus__is_active=True)


def require_faculty(actor, capability=None):
    current = User.objects.select_related("role").filter(pk=getattr(actor, "pk", None)).first()
    if (
        current is None
        or not current.is_active
        or current.role.code != "FACULTY"
        or (capability is not None and not current.has_capability(capability))
    ):
        raise FacultyReferralError("not_permitted")
    return current


def require_faculty_home(actor):
    home = (
        FacultyAffiliation.objects.select_related("college__campus")
        .select_for_update(of=("self",))
        .filter(faculty=actor)
        .first()
    )
    if (
        home is None
        or home.college is None
        or not home.college.is_active
        or not home.college.campus.is_active
    ):
        raise FacultyReferralError("affiliation_unavailable")
    return home


def faculty_can_track(actor):
    current = User.objects.select_related("role").filter(pk=getattr(actor, "pk", None)).first()
    return bool(
        current is not None
        and current.is_active
        and current.role.code == "FACULTY"
        and current.has_capability("referrals.view_submitted_self")
        and FacultyAffiliation.objects.filter(
            faculty=current, college__is_active=True, college__campus__is_active=True
        ).exists()
    )


def require_administration(actor, *, manage=False):
    if (
        actor is None
        or not actor.is_active
        or actor.role.code not in ADMINISTRATIVE_ROLES
        or not actor.has_capability("referrals.view")
        or (manage and not actor.has_capability("referrals.manage"))
    ):
        raise AdministrativeReferralError("not_permitted")
    return actor
