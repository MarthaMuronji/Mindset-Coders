from .models import AuditEvent


def record_audit_event(
    action,
    user=None,
    object_type='',
    object_id='',
    detail='',
    username=None,
):
    if username is None:
        username = user.get_username() if user and user.is_authenticated else ''
    return AuditEvent.objects.create(
        user=user if user and user.is_authenticated else None,
        username=username[:150],
        action=action,
        object_type=object_type[:100],
        object_id=str(object_id)[:100],
        detail=detail[:200],
    )
