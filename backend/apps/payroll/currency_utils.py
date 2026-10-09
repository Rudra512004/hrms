"""
Monetary amount-to-words conversion suitable for INR (Indian Rupees).
Uses Decimal input with deterministic rounding (ROUND_HALF_UP).
"""
from decimal import Decimal, ROUND_HALF_UP

UNITS = [
    '', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
    'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
    'Seventeen', 'Eighteen', 'Nineteen'
]
TENS = [
    '', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'
]


def _two_digits(n: int) -> str:
    if n < 20:
        return UNITS[n]
    tens_str = TENS[n // 10]
    unit_str = UNITS[n % 10]
    return f"{tens_str}-{unit_str}" if unit_str else tens_str


def _three_digits(n: int) -> str:
    if n >= 100:
        h = f"{UNITS[n // 100]} Hundred"
        rem = n % 100
        return f"{h} and {_two_digits(rem)}" if rem else h
    return _two_digits(n)


def amount_to_words_inr(amount: Decimal) -> str:
    """
    Converts a Decimal amount into words using the Indian numbering system.
    Examples:
        Decimal('0.00') -> 'Zero Rupees Only'
        Decimal('1.00') -> 'One Rupee Only'
        Decimal('55000.00') -> 'Fifty-Five Thousand Rupees Only'
        Decimal('55000.50') -> 'Fifty-Five Thousand Rupees and Fifty Paise Only'
        Decimal('0.50') -> 'Fifty Paise Only'
        Decimal('0.01') -> 'One Paisa Only'
        Decimal('100000.00') -> 'One Lakh Rupees Only'
        Decimal('105000000.00') -> 'Ten Crore Fifty Lakh Rupees Only'
    """
    if amount is None:
        return ""

    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    if amount < 0:
        raise ValueError("Amount cannot be negative.")

    if amount == Decimal('0.00'):
        return "Zero Rupees Only"

    rupees = int(amount)
    paise = int((amount - Decimal(rupees)) * 100)

    words = []
    crore = rupees // 10000000
    rem = rupees % 10000000
    lakh = rem // 100000
    rem = rem % 100000
    thousand = rem // 1000
    rem = rem % 1000
    hundred = rem

    if crore > 0:
        words.append(f"{_three_digits(crore)} Crore")
    if lakh > 0:
        words.append(f"{_two_digits(lakh)} Lakh")
    if thousand > 0:
        words.append(f"{_two_digits(thousand)} Thousand")
    if hundred > 0:
        words.append(_three_digits(hundred))

    rupee_part = " ".join(words).strip()
    if rupee_part:
        rupee_str = f"{rupee_part} Rupee" if rupees == 1 else f"{rupee_part} Rupees"
    else:
        rupee_str = ""

    if paise > 0:
        paise_str = f"{_two_digits(paise)} Paisa" if paise == 1 else f"{_two_digits(paise)} Paise"
        if rupee_str:
            return f"{rupee_str} and {paise_str} Only"
        return f"{paise_str} Only"

    return f"{rupee_str} Only"
