"""Fixed Good Moral certificate fees."""

from decimal import Decimal

from .models import GoodMoralVariant

GOOD_MORAL_FEE = Decimal("80.00")
GOOD_MORAL_CURRENCY = "PHP"
FEE_VARIANTS = frozenset(
    {
        GoodMoralVariant.CURRENT_STUDENT,
        GoodMoralVariant.GRADUATE,
    }
)


def expected_amount_for(request) -> Decimal:
    """Return the fixed fee for an F4 or F6 Good Moral request."""

    if request.variant not in FEE_VARIANTS:
        raise ValueError(f"Unsupported Good Moral variant: {request.variant!r}")
    return GOOD_MORAL_FEE
