from collections.abc import Sequence
from functools import wraps
from typing import ClassVar

from django.contrib import admin
from django.contrib import messages
from django.db.models import F
from django.shortcuts import redirect
from django.utils import timezone

from .audit import record_audit_event
from .models import (
    AuditEvent,
    ContactMessage,
    LoginThrottle,
    Post,
    Registration,
    Story,
)
from .throttle import (
    locked_message,
    locked_seconds,
    record_failure,
    reset_username_key,
)


_admin_login = admin.site.login


@wraps(_admin_login)
def _throttled_admin_login(request, *args, **kwargs):
    if request.method != 'POST':
        return _admin_login(request, *args, **kwargs)

    username = request.POST.get('username', '')
    seconds = locked_seconds(request, username)
    if seconds:
        messages.error(request, locked_message(seconds))
        return redirect(request.get_full_path())

    response = _admin_login(request, *args, **kwargs)
    if response.status_code == 200:
        record_audit_event(
            'failed_sign_in',
            username=username.strip(),
            detail='Sign in failed',
        )
        record_failure(request, username)
    elif 300 <= response.status_code < 400:
        reset_username_key(request, username)
    return response


admin.site.login = _throttled_admin_login


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'published', 'created_at')
    list_filter = ('published',)
    search_fields = ('title', 'excerpt', 'content')
    prepopulated_fields: ClassVar[dict[str, Sequence[str]]] = {'slug': ('title',)}


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'created_at', 'handled')
    list_filter = ('handled',)
    search_fields = ('name', 'email', 'phone', 'message')
    # Messages arrive from the form, so nothing but the handled flag is editable
    readonly_fields = ('name', 'email', 'phone', 'role', 'message', 'created_at')


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        'learner_name', 'parent_name', 'parent_email', 'programme', 'stage',
        'payment_method', 'payment_status', 'amount_due', 'amount_paid',
        'balance', 'created_at', 'handled',
    )
    list_filter = (
        'handled', 'programme', 'stage', 'payment_method', 'payment_status',
    )
    search_fields = (
        'parent_name', 'learner_name', 'parent_email', 'receipt_number',
    )
    readonly_fields = (
        'parent_name', 'parent_email', 'parent_phone', 'learner_name',
        'learner_age', 'school_name', 'programme', 'stage', 'consent', 'created_at',
        'payment_method', 'amount_due', 'paid_at', 'balance',
        'payment_recorded_by',
    )
    actions = ('mark_as_paid', 'mark_as_cancelled')

    @admin.display(description='Balance')
    def balance(self, registration):
        return max((registration.amount_due or 0) - registration.amount_paid, 0)

    @admin.action(description='Mark as paid')
    def mark_as_paid(self, request, queryset):
        now = timezone.now()
        eligible = queryset.exclude(amount_due__isnull=True)
        count = eligible.update(
            payment_status='paid',
            amount_paid=F('amount_due'),
            paid_at=now,
        )
        skipped = queryset.count() - count
        message = 'Marked {} {} as paid.'.format(
            count, 'registration' if count == 1 else 'registrations'
        )
        if skipped:
            message += f' {skipped} without an amount due were skipped.'
        self.message_user(request, message)

    @admin.action(description='Mark as cancelled')
    def mark_as_cancelled(self, request, queryset):
        count = queryset.update(payment_status='cancelled')
        self.message_user(
            request,
            'Marked {} {} as cancelled.'.format(
                count, 'registration' if count == 1 else 'registrations'
            ),
        )


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    # name and email stay off the list, but the team can open a story to reply
    list_display = ('created_at', 'name', 'category', 'role', 'approved')
    list_filter = ('approved', 'category')
    search_fields = ('name', 'story')
    # The review area owns the review marks, so the admin only shows them
    readonly_fields = ('rejected', 'reviewed_at', 'reviewed_by')
    actions = ('approve_selected', 'unapprove_selected')

    @admin.action(description='Approve selected')
    def approve_selected(self, request, queryset):
        count = queryset.update(
            approved=True,
            rejected=False,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, 'Approved {} selected {}.'.format(count, 'story' if count == 1 else 'stories'))

    @admin.action(description='Unapprove selected')
    def unapprove_selected(self, request, queryset):
        # Back to waiting, with the review marks cleared
        count = queryset.update(
            approved=False,
            rejected=False,
            reviewed_at=None,
            reviewed_by=None,
        )
        self.message_user(request, 'Unapproved {} selected {}.'.format(count, 'story' if count == 1 else 'stories'))


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'username', 'action', 'object_type', 'object_id')
    list_filter = ('action', 'created_at')
    search_fields = ('username', 'object_type', 'object_id', 'detail')
    readonly_fields = (
        'created_at', 'user', 'username', 'action', 'object_type',
        'object_id', 'detail',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LoginThrottle)
class LoginThrottleAdmin(admin.ModelAdmin):
    list_display = ('key', 'failures', 'locked_until', 'updated_at')
    readonly_fields = ('key', 'failures', 'locked_until', 'updated_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
