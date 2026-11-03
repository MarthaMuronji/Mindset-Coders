import hashlib
import hmac
from datetime import timedelta
from math import ceil

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .audit import record_audit_event
from .models import LoginThrottle
from .spam import _visitor_ip


FAILURE_WINDOW = timedelta(hours=1)
THROTTLE_RETENTION = timedelta(days=7)
USERNAME_IP_THRESHOLD = 5
IP_THRESHOLD = 20
MAX_LOCK_SECONDS = 900


def _normalized_username(username):
    return (username or '').strip().lower()


def _digest(value):
    return hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        value.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def _throttle_keys(request, username):
    address = _visitor_ip(request)
    normalized_username = _normalized_username(username)
    return (
        _digest('username:{}\0{}'.format(normalized_username, address)),
        _digest('ip:{}'.format(address)),
    )


def _seconds_left(locked_until, now):
    if locked_until is None or locked_until <= now:
        return 0
    return min(MAX_LOCK_SECONDS, ceil((locked_until - now).total_seconds()))


def locked_seconds(request, username):
    now = timezone.now()
    keys = _throttle_keys(request, username)
    locks = LoginThrottle.objects.filter(
        key__in=keys,
        locked_until__gt=now,
    ).values_list('locked_until', flat=True)
    return max((_seconds_left(value, now) for value in locks), default=0)


def record_failure(request, username):
    now = timezone.now()
    normalized_username = _normalized_username(username)
    keys = _throttle_keys(request, normalized_username)
    thresholds = (USERNAME_IP_THRESHOLD, IP_THRESHOLD)
    new_locks = []

    for key, threshold in zip(keys, thresholds):
        with transaction.atomic():
            try:
                row, _ = LoginThrottle.objects.get_or_create(key=key)
            except IntegrityError:
                row = LoginThrottle.objects.get(key=key)
            row = LoginThrottle.objects.select_for_update().get(pk=row.pk)

            if row.locked_until and row.locked_until > now:
                continue
            if now - row.updated_at > FAILURE_WINDOW:
                row.failures = 0
                row.locked_until = None
                update_locked_until = True
            else:
                update_locked_until = False

            row.failures += 1
            update_fields = ['failures', 'updated_at']
            if update_locked_until:
                update_fields.append('locked_until')
            if row.failures >= threshold:
                lock_seconds = min(
                    30 * (2 ** (row.failures - threshold)),
                    MAX_LOCK_SECONDS,
                )
                row.locked_until = now + timedelta(seconds=lock_seconds)
                if 'locked_until' not in update_fields:
                    update_fields.append('locked_until')
                new_locks.append(key)
            row.save(update_fields=update_fields)

    LoginThrottle.objects.filter(updated_at__lt=now - THROTTLE_RETENTION).delete()
    for _ in new_locks:
        record_audit_event(
            'login_locked',
            username=normalized_username,
            detail='Sign-in attempts temporarily locked',
        )


def reset_username_key(request, username):
    username_key, _ = _throttle_keys(request, username)
    LoginThrottle.objects.filter(key=username_key).delete()


def locked_message(seconds):
    return 'Too many attempts. Please wait {} seconds and try again.'.format(
        min(MAX_LOCK_SECONDS, max(1, seconds))
    )
