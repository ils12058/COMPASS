"""Code-owned, team-reported provisional PHP 80 fee for F4 and F6.

Definitions are versioned by receipt date. Retain this definition when adding a
future schedule so inspection and issuance preserve their historical evidence.
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
            self.status in {"APPROVED", "PROVISIONAL"}
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
    """Resolve the immutable team-reported definition using the receipt date.

    The provisional definition covers all receipt dates until a future versioned
    schedule supplies a bounded successor. Its status is not institutional approval.
    """
    if item.variant not in TEAM_REPORTED_VARIANTS or assignment.receipt_date is None:
        return None
    return FeeDecision(
        policy_id="GOOD_MORAL_TEAM_REPORTED_PROVISIONAL",
        version="1",
        currency=TEAM_REPORTED_CURRENCY,
        expected_amount=TEAM_REPORTED_AMOUNT,
        authority_reference="Team-reported provisional PHP 80.00 for F4 and F6",
        variant=item.variant,
        reference_date=assignment.receipt_date,
        applicable_from=date.min,
        applicable_through=date.max,
        status="PROVISIONAL",
    )
