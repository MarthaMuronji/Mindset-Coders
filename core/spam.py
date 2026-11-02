import hashlib
import hmac
import ipaddress
import time

from django.conf import settings
from django.core import signing
from django.core.cache import cache


FORM_TIMESTAMP_SALT = 'core.public_form_timestamp'
FORM_MIN_AGE_SECONDS = 3
FORM_MAX_AGE_SECONDS = 24 * 60 * 60
CONTACT_SUBMISSIONS_PER_HOUR = 5
CONTACT_RATE_LIMIT_WINDOW_SECONDS = 60 * 60


def _validated_ip(value):
    try:
        return str(ipaddress.ip_address(value.strip()))
    except (AttributeError, ValueError):
        return None


def _visitor_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        forwarded_ip = _validated_ip(forwarded_for.split(',', 1)[0])
        if forwarded_ip:
            return forwarded_ip

    remote_addr = request.META.get('REMOTE_ADDR', '')
    return _validated_ip(remote_addr) or remote_addr


def create_form_timestamp():
    return signing.TimestampSigner(salt=FORM_TIMESTAMP_SALT).sign(
        str(time.time())
    )


def is_form_timestamp_valid(value):
    try:
        signed_at = signing.TimestampSigner(
            salt=FORM_TIMESTAMP_SALT
        ).unsign(value, max_age=FORM_MAX_AGE_SECONDS)
        age = time.time() - float(signed_at)
    except (signing.BadSignature, TypeError, ValueError):
        return False
    return FORM_MIN_AGE_SECONDS <= age <= FORM_MAX_AGE_SECONDS


def contact_rate_limit_exceeded(request):
    address = _visitor_ip(request)
    address_hash = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        address.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    key = 'contact-form-rate:{}'.format(address_hash)
    # Vercel's per-instance memory cache makes this a soft limit across instances.
    cache.add(key, 0, timeout=CONTACT_RATE_LIMIT_WINDOW_SECONDS)
    return cache.incr(key) > CONTACT_SUBMISSIONS_PER_HOUR
