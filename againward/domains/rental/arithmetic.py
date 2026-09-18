"""Fixed Decimal context, independent of callers' precision/rounding settings."""
from decimal import Context, DecimalException, ROUND_HALF_UP, localcontext
from functools import wraps


def deterministic_decimal(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            with localcontext(Context(prec=128, rounding=ROUND_HALF_UP)):
                return function(*args, **kwargs)
        except DecimalException as exc:
            raise ValueError("Rental arithmetic outside supported decimal bounds.") from exc
    return wrapped
