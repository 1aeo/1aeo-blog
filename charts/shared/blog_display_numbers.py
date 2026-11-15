"""Public display precision only; never feed formatted values into analysis."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from fractions import Fraction

def decimal_value(value):
    if isinstance(value,Fraction):
        with localcontext() as ctx:
            ctx.prec=50
            return Decimal(value.numerator)/Decimal(value.denominator)
    return value if isinstance(value,Decimal) else Decimal(str(value))

def _measurement(value):
    # Keep rational comparisons exact at majority and ratio boundaries.
    if isinstance(value,Fraction):return value
    try:value=decimal_value(value)
    except (InvalidOperation,TypeError,ValueError) as error:
        raise ValueError('Measurement must be numeric') from error
    if not value.is_finite():raise ValueError('Measurement must be finite')
    return value

def _whole(value):
    if isinstance(value,Fraction):
        quotient,remainder=divmod(abs(value.numerator),value.denominator)
        rounded=quotient+(2*remainder>=value.denominator)
        return -rounded if value<0 else rounded
    # Unlike quantize(), integral rounding does not fail for large counters
    # or a caller's small Decimal context precision.
    return int(value.to_integral_value(rounding=ROUND_HALF_UP))

def number(value, grouping=True):
    """Whole units, with zero distinguished from a positive sub-unit value."""
    if value is None:return 'Unavailable'
    value=_measurement(value)
    if not value:return '0'
    if 0<value<1:return '<1'
    if -1<value<0:return '>−1'
    rounded=_whole(value)
    return f'{rounded:,}' if grouping else str(rounded)

def percentage(value, suffix=True, boundaries=(50,100)):
    """Whole bounded shares without moving a value across a meaningful cutoff.

    Use boundaries=(90,95,100) for the measured-time distribution. Exact100
    stays100; a rounded non-total share is >99, not a false claim of unanimity.
    CPU utilization is unbounded and must use number(), not this function.
    """
    if value is None:return 'Unavailable'
    value=_measurement(value)
    if not 0<=value<=100:raise ValueError('Percentage must be between 0 and 100')
    rounded=_whole(value)
    if 0<value<1:label='<1'
    elif value<100 and rounded==100:label='>99'
    else:
        label=str(rounded)
        for boundary in boundaries:
            if rounded==boundary and value!=boundary:
                label=('<' if value<boundary else '>')+str(rounded)
                # Values just above95 are already in the95–<100 bin, so95 is
                # a faithful rounded display; strict-majority50 is different.
                if value>boundary and boundary!=50:label=str(rounded)
                break
    return label+('%' if suffix else '')

def ratio(value):
    if value is None:return 'Unavailable'
    value=_measurement(value)
    if 1<value<Decimal('1.5'):return '>1'
    return number(value)

def signed_percent(value):
    if value is None:return 'Unavailable'
    value=_measurement(value)
    if 0<value<1:return '<+1%'
    if -1<value<0:return '>−1%'
    sign='+' if value>0 else '−' if value<0 else ''
    magnitude=value.copy_abs() if isinstance(value,Decimal) else abs(value)
    return sign+number(magnitude)+'%'
