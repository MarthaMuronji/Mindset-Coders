import re


PHONE_ERROR = (
    'Please enter a valid phone number, for example 0772 123 456 '
    'or +256 772 123 456.'
)

_DECORATIONS = re.compile(r'[\s\-()\[\]]')
_DIGITS_ONLY = re.compile(r'\+?[0-9]+')
_UGANDAN_INTERNATIONAL = re.compile(r'^\+256[37][0-9]{8}$')
_UGANDAN_LOCAL = re.compile(r'^0[37][0-9]{8}$')
_UGANDAN_PREFIXED = re.compile(r'^256[37][0-9]{8}$')


def normalize_phone_number(value):
    number = _DECORATIONS.sub('', value)
    if not _DIGITS_ONLY.fullmatch(number):
        raise ValueError(PHONE_ERROR)

    if number.startswith('+'):
        digits = number[1:]
        if not 8 <= len(digits) <= 15 or digits.startswith('0'):
            raise ValueError(PHONE_ERROR)
        if digits.startswith('256'):
            if not _UGANDAN_INTERNATIONAL.fullmatch(number):
                raise ValueError(PHONE_ERROR)
            subscriber = digits[4:]
            if len(set(subscriber)) == 1:
                raise ValueError(PHONE_ERROR)
        elif len(set(digits)) == 1:
            raise ValueError(PHONE_ERROR)
        return '+' + digits

    if _UGANDAN_PREFIXED.fullmatch(number):
        if len(set(number[4:])) == 1:
            raise ValueError(PHONE_ERROR)
        return '+' + number

    if _UGANDAN_LOCAL.fullmatch(number):
        if len(set(number[2:])) == 1:
            raise ValueError(PHONE_ERROR)
        return '+256' + number[1:]

    raise ValueError(PHONE_ERROR)
