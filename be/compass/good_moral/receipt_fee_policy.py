"""Code-owned expected-fee decisions. No approved institutional schedule is installed.

The operational provider deliberately returns None. Synthetic tests inject a bounded
approved definition; neither environment flags nor API payloads can approve pricing.
"""

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal

TEAM_REPORTED_AMOUNT = Decimal("80.00")
TEAM_REPORTED_CURRENCY = "PHP"
TEAM_REPORTED_VARIANTS = frozenset({"CURRENT_STUDENT", "GRADUATE"})


@dataclass(frozen=True)
class FeeDecision:
    policy_id: str
    version: str
    currency: str
    expected_amount: Decimal
    authority_reference: str
    variant: str
    reference_date: date
    applicable_from: date
    applicable_through: date
    applicability_rule: str = "RECEIPT_DATE_IN_APPROVED_RANGE"
    status: str = "APPROVED"

    def snapshot(self):
        return {k: str(v) for k, v in asdict(self).items()}

    def applies(self, item, assignment):
        return (
            self.status == "APPROVED"
            and bool(self.policy_id and self.version and self.authority_reference)
            and self.currency == "PHP"
            and self.variant == item.variant
            and self.variant in TEAM_REPORTED_VARIANTS
            and self.applicability_rule == "RECEIPT_DATE_IN_APPROVED_RANGE"
            and isinstance(self.reference_date, date)
            and isinstance(self.applicable_from, date)
            and isinstance(self.applicable_through, date)
            and self.reference_date == assignment.receipt_date
            and self.applicable_from <= self.reference_date <= self.applicable_through
            and isinstance(self.expected_amount, Decimal)
            and self.expected_amount.is_finite()
            and 0 < self.expected_amount < Decimal("10000000000")
            and self.expected_amount.as_tuple().exponent >= -2
        )


def resolve_approved_fee(*, item, assignment) -> FeeDecision | None:
    """Release boundary: requires separately reviewed institutional definitions/authority.

    Retain historical definitions when adding a real schedule. There is deliberately
    no effective date for the team's PHP 80 report and no operational activation flag.
    """
    return None
