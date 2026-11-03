from functools import wraps
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.db.models import Q
from django.forms.utils import ErrorDict
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods

from .audit import record_audit_event
from .models import ContactMessage, Registration
from .middleware import IDLE_SIGN_OUT_MESSAGE
from .throttle import (
    locked_message,
    locked_seconds,
    record_failure,
    reset_username_key,
)


REGISTRATION_STATUSES = {
    'pending': 'Waiting for payment',
    'part_paid': 'Part paid',
    'paid': 'Paid',
    'cancelled': 'Cancelled',
}
REGISTRATION_FILTERS = ('pending', 'part_paid', 'paid', 'cancelled')
METHOD_FILTERS = ('online', 'cash')
FOLLOW_UP_FILTERS = ('no', 'yes', 'all')
REGISTRATION_ACTIONS = ('paid', 'part_paid', 'cancel', 'anonymise')
ACTION_TITLES = {
    'paid': 'Mark as paid in full',
    'part_paid': 'Record part payment',
    'cancel': 'Cancel registration',
    'anonymise': 'Remove personal details',
}


def private_team_page(view):
    """Keep every team response private, including redirects and errors."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
    return never_cache(wrapped)


def _login_url(next_url):
    return '{}?{}'.format(
        reverse('team_login'),
        urlencode({'next': next_url}),
    )


def _allowed(request, permission):
    return (
        request.user.is_authenticated
        and request.user.is_active
        and request.user.has_perm(permission)
    )


def _deny_or_login(request):
    if request.user.is_authenticated:
        return render(
            request,
            'team/denied.html',
            {'page_title': 'No access'},
            status=403,
        )
    return redirect(_login_url(request.get_full_path()))


def _require_permission(request, permission):
    if _allowed(request, permission):
        return None
    return _deny_or_login(request)


class TeamLoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'That username and password did not match. Please try again.',
    }

    def add_sign_in_notice(self, message):
        self._errors = ErrorDict()
        self.cleaned_data = {}
        self.add_error(None, message)


@method_decorator(private_team_page, name='dispatch')
class TeamLoginView(LoginView):
    template_name = 'team/login.html'
    authentication_form = TeamLoginForm
    redirect_authenticated_user = True
    next_page = reverse_lazy('team_home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Team sign in'
        pending_messages = get_messages(self.request)
        for message in pending_messages:
            if str(message) == IDLE_SIGN_OUT_MESSAGE:
                context['form'].add_sign_in_notice(str(message))
        return context

    def post(self, request, *args, **kwargs):
        seconds = locked_seconds(request, request.POST.get('username', ''))
        if seconds:
            form = self.get_form()
            form.add_sign_in_notice(locked_message(seconds))
            return self.render_to_response(self.get_context_data(form=form))
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        reset_username_key(
            self.request,
            form.cleaned_data.get('username', ''),
        )
        record_audit_event(
            'sign_in',
            user=self.request.user,
            object_type='User',
            object_id=self.request.user.pk,
            detail='Signed in',
        )
        return response

    def form_invalid(self, form):
        username = self.request.POST.get('username', '').strip()
        record_audit_event(
            'failed_sign_in',
            username=username,
            detail='Sign in failed',
        )
        record_failure(self.request, username)
        return super().form_invalid(form)


team_logout = private_team_page(
    LogoutView.as_view(next_page=reverse_lazy('team_login'))
)


@private_team_page
def team_home(request):
    if not request.user.is_authenticated:
        return redirect(_login_url(request.get_full_path()))
    can_view_full = (
        _allowed(request, 'core.view_registration')
        or _allowed(request, 'core.view_full_registration')
    )
    can_view_finance = _allowed(request, 'core.view_finance_fields')
    can_view_registrations = can_view_full or can_view_finance
    can_view_messages = _allowed(request, 'core.view_contactmessage')
    can_view_roster = (
        _allowed(request, 'core.view_roster')
        or _allowed(request, 'core.view_full_registration')
    )
    can_manage_team = _allowed(request, 'core.manage_team')
    can_view_audit = _allowed(request, 'core.view_audit_log')
    if not any((can_view_registrations, can_view_messages, can_view_roster, can_manage_team, can_view_audit)):
        return _deny_or_login(request)
    return render(request, 'team/home.html', {
        'page_title': 'Team home',
        'can_view_registrations': can_view_registrations,
        'can_view_roster': can_view_roster,
        'can_view_messages': can_view_messages,
        'can_manage_team': can_manage_team,
        'can_view_audit': can_view_audit,
    })


def _registration_context(registration):
    due = registration.amount_due or 0
    balance = max(due - registration.amount_paid, 0)
    return {
        'registration': registration,
        'balance': balance,
        'status_label': REGISTRATION_STATUSES.get(
            registration.payment_status,
            registration.get_payment_status_display(),
        ),
        'phone_tel': _phone_tel(registration.parent_phone),
        'phone_whatsapp': _phone_whatsapp(registration.parent_phone),
    }


def _phone_tel(phone):
    digits = ''.join(character for character in phone if character.isdigit())
    if phone.strip().startswith('+'):
        return '+{}'.format(digits)
    if digits.startswith('00'):
        return '+{}'.format(digits[2:])
    if digits.startswith('0') and digits:
        return '+256{}'.format(digits[1:])
    return '+{}'.format(digits) if digits else ''


def _phone_whatsapp(phone):
    return _phone_tel(phone).lstrip('+')


@private_team_page
def registration_list(request):
    can_view_full = (
        _allowed(request, 'core.view_registration')
        or _allowed(request, 'core.view_full_registration')
    )
    if not can_view_full and not _allowed(request, 'core.view_finance_fields'):
        return _deny_or_login(request)

    registrations = Registration.objects.all()
    status = request.GET.get('status', '')
    method = request.GET.get('method', '')
    stage = request.GET.get('stage', '')
    search = request.GET.get('q', '').strip()
    if status in REGISTRATION_FILTERS:
        registrations = registrations.filter(payment_status=status)
    else:
        status = ''
    if method in METHOD_FILTERS:
        registrations = registrations.filter(payment_method=method)
    else:
        method = ''
    stages = {key for key, _label in Registration.STAGE_CHOICES}
    if stage not in stages:
        stage = ''
    if stage:
        registrations = registrations.filter(stage=stage)
    if search:
        registrations = registrations.filter(
            Q(parent_name__icontains=search)
            | Q(learner_name__icontains=search)
            | Q(parent_phone__icontains=search)
            | Q(receipt_number__icontains=search)
        )
    items = list(registrations)
    for registration in items:
        registration.balance = max(
            (registration.amount_due or 0) - registration.amount_paid,
            0,
        )
        registration.status_label = REGISTRATION_STATUSES.get(
            registration.payment_status,
            registration.get_payment_status_display(),
        )
    return render(request, 'team/registrations.html', {
        'page_title': 'Registrations',
        'registrations': items,
        'status': status,
        'method': method,
        'stage': stage,
        'search': search,
        'status_choices': REGISTRATION_STATUSES.items(),
        'method_choices': Registration.PAYMENT_METHOD_CHOICES,
        'stage_choices': Registration.STAGE_CHOICES,
        'counts': {
            'pending': Registration.objects.filter(
                payment_status='pending'
            ).count(),
            'paid': Registration.objects.filter(
                payment_status='paid'
            ).count(),
            'cancelled': Registration.objects.filter(
                payment_status='cancelled'
            ).count(),
        },
        'can_change': _allowed(request, 'core.change_registration'),
        'can_view_full': can_view_full,
    })


@private_team_page
@require_http_methods(['GET', 'POST'])
def registration_detail(request, pk):
    can_view_full = (
        _allowed(request, 'core.view_registration')
        or _allowed(request, 'core.view_full_registration')
    )
    can_view_finance = _allowed(request, 'core.view_finance_fields')
    if not can_view_full and not can_view_finance:
        return _deny_or_login(request)
    registration = get_object_or_404(Registration, pk=pk)
    if request.method == 'POST':
        denied = _require_permission(request, 'core.change_registration')
        if denied:
            return denied
        registration.payment_note = request.POST.get('payment_note', '').strip()
        registration.save(update_fields=['payment_note'])
        messages.success(request, 'Internal note saved.')
        return redirect('team_registration_detail', pk=registration.pk)
    record_audit_event(
        'registration_opened',
        user=request.user,
        object_type='Registration',
        object_id=registration.pk,
        detail='Registration details opened',
    )
    context = _registration_context(registration)
    context.update({
        'page_title': 'Registration details',
        'can_view_full': can_view_full,
        'can_view_finance': can_view_finance,
        'can_change': _allowed(request, 'core.change_registration'),
        'can_record_payment': (
            _allowed(request, 'core.record_payment')
            or _allowed(request, 'core.change_registration')
        ),
        'can_anonymise': _allowed(request, 'core.anonymise_registration'),
        'status_choices': REGISTRATION_STATUSES,
    })
    return render(request, 'team/registration_detail.html', context)


class RegistrationActionForm(forms.Form):
    amount = forms.IntegerField(
        min_value=1,
        required=False,
        label='Amount received (UGX)',
    )
    receipt_number = forms.CharField(
        max_length=100,
        required=False,
        label='Receipt number',
    )
    note = forms.CharField(
        required=False,
        label='Internal note',
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, action, registration, **kwargs):
        self.action = action
        self.registration = registration
        balance = max(
            (registration.amount_due or 0) - registration.amount_paid,
            0,
        )
        super().__init__(*args, **kwargs)
        if action in ('paid', 'part_paid'):
            self.fields['amount'].initial = balance
            self.fields['receipt_number'].required = False
        if action != 'paid':
            self.fields.pop('note')
        if action == 'cancel':
            self.fields.clear()

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        balance = max(
            (self.registration.amount_due or 0)
            - self.registration.amount_paid,
            0,
        )
        if amount is None:
            amount = balance
        if self.action == 'paid' and amount != balance:
            raise forms.ValidationError(
                'Enter the remaining balance to mark this registration paid in full.'
            )
        if self.action == 'part_paid' and amount >= balance:
            raise forms.ValidationError(
                'A part payment must be less than the remaining balance.'
            )
        return amount


@private_team_page
@transaction.atomic
@require_POST
def registration_action(request, pk, action):
    if action not in REGISTRATION_ACTIONS:
        raise Http404
    has_registration_access = any((
        _allowed(request, 'core.view_registration'),
        _allowed(request, 'core.view_full_registration'),
        _allowed(request, 'core.view_finance_fields'),
    ))
    if not has_registration_access:
        return _deny_or_login(request)
    if action == 'anonymise':
        denied = _require_permission(request, 'core.anonymise_registration')
    elif (
        _allowed(request, 'core.record_payment')
        or _allowed(request, 'core.change_registration')
    ):
        denied = None
    else:
        denied = _deny_or_login(request)
    if denied:
        return denied
    registration = get_object_or_404(Registration, pk=pk)
    confirmed = request.POST.get('confirmed') == 'true'
    form = RegistrationActionForm(
        request.POST if confirmed else None,
        action=action,
        registration=registration,
    )
    if action == 'anonymise':
        form.fields.clear()
    if confirmed:
        if not form.is_valid():
            return render(request, 'team/action_confirm.html', {
                **_registration_context(registration),
                'page_title': ACTION_TITLES[action],
                'action': action,
                'action_title': ACTION_TITLES[action],
                'form': form,
            }, status=400)
        now = timezone.now()
        old_status = registration.payment_status
        if action == 'paid':
            registration.payment_status = 'paid'
            registration.amount_paid = registration.amount_due or 0
            registration.paid_at = now
            registration.payment_recorded_by = request.user.get_username()
            receipt = form.cleaned_data.get('receipt_number')
            note = form.cleaned_data.get('note')
            if receipt:
                registration.receipt_number = receipt
            if note:
                registration.payment_note = note
            registration.save(update_fields=[
                'payment_status', 'amount_paid', 'paid_at',
                'payment_recorded_by', 'receipt_number', 'payment_note',
            ])
            messages.success(request, 'Payment recorded. The registration is paid in full.')
            record_audit_event(
                'payment_recorded',
                user=request.user,
                object_type='Registration',
                object_id=registration.pk,
                detail='Payment recorded',
            )
        elif action == 'part_paid':
            registration.payment_status = 'part_paid'
            registration.amount_paid += form.cleaned_data['amount']
            registration.paid_at = now
            registration.payment_recorded_by = request.user.get_username()
            receipt = form.cleaned_data.get('receipt_number')
            if receipt:
                registration.receipt_number = receipt
            registration.save(update_fields=[
                'payment_status', 'amount_paid', 'paid_at',
                'payment_recorded_by', 'receipt_number',
            ])
            messages.success(request, 'Part payment recorded.')
            record_audit_event(
                'payment_recorded',
                user=request.user,
                object_type='Registration',
                object_id=registration.pk,
                detail='Part payment recorded',
            )
        elif action == 'cancel':
            registration.payment_status = 'cancelled'
            registration.paid_at = now
            registration.payment_recorded_by = request.user.get_username()
            registration.save(update_fields=[
                'payment_status', 'paid_at', 'payment_recorded_by',
            ])
            messages.success(request, 'Registration cancelled.')
        else:
            registration.learner_name = 'Removed'
            registration.parent_name = 'Removed'
            registration.parent_email = 'Removed'
            registration.parent_phone = 'Removed'
            registration.school_name = ''
            registration.save(update_fields=[
                'learner_name', 'parent_name', 'parent_email',
                'parent_phone', 'school_name',
            ])
            messages.success(request, 'Personal details removed from this registration.')
            record_audit_event(
                'anonymised',
                user=request.user,
                object_type='Registration',
                object_id=registration.pk,
                detail='Registration anonymised',
            )
        if action != 'anonymise' and old_status != registration.payment_status:
            record_audit_event(
                'status_changed',
                user=request.user,
                object_type='Registration',
                object_id=registration.pk,
                detail='Registration status changed',
            )
        return redirect('team_registration_detail', pk=registration.pk)

    return render(request, 'team/action_confirm.html', {
        **_registration_context(registration),
        'page_title': ACTION_TITLES[action],
        'action': action,
        'action_title': ACTION_TITLES[action],
        'form': form,
    })


@private_team_page
def message_list(request):
    denied = _require_permission(request, 'core.view_contactmessage')
    if denied:
        return denied
    follow_up = request.GET.get('follow_up', 'no')
    if follow_up not in FOLLOW_UP_FILTERS:
        follow_up = 'no'
    messages_qs = ContactMessage.objects.all()
    if follow_up == 'yes':
        messages_qs = messages_qs.filter(handled=True)
    elif follow_up == 'no':
        messages_qs = messages_qs.filter(handled=False)
    items = list(messages_qs)
    for message in items:
        message.phone_tel = _phone_tel(message.phone or '')
        message.phone_whatsapp = _phone_whatsapp(message.phone or '')
    return render(request, 'team/messages.html', {
        'page_title': 'Contact messages',
        'contact_messages': items,
        'follow_up': follow_up,
        'can_change': _allowed(request, 'core.change_contactmessage'),
    })


@private_team_page
@transaction.atomic
@require_POST
def message_follow_up(request, pk):
    denied = _require_permission(request, 'core.view_contactmessage')
    if denied:
        return denied
    denied = _require_permission(request, 'core.change_contactmessage')
    if denied:
        return denied
    contact_message = get_object_or_404(ContactMessage, pk=pk)
    was_handled = contact_message.handled
    handled = request.POST.get('handled') == 'true'
    contact_message.handled = handled
    contact_message.save(update_fields=['handled'])
    if handled and not was_handled:
        record_audit_event(
            'message_followed_up',
            user=request.user,
            object_type='ContactMessage',
            object_id=contact_message.pk,
            detail='Message marked followed up',
        )
    messages.success(
        request,
        'Message marked as followed up.' if handled else 'Message marked as not followed up.',
    )
    return redirect('{}?{}'.format(
        reverse('team_messages'),
        urlencode({'follow_up': request.POST.get('follow_up', 'no')}),
    ))


def _can_view_roster(request):
    return (
        _allowed(request, 'core.view_roster')
        or _allowed(request, 'core.view_full_registration')
    )


@private_team_page
def roster_list(request):
    if not _can_view_roster(request):
        return _deny_or_login(request)
    valid_stages = {value for value, _label in Registration.STAGE_CHOICES}
    stage = request.GET.get('stage', 'discover')
    if stage not in valid_stages:
        stage = 'discover'
    learners = Registration.objects.filter(stage=stage).order_by(
        'learner_name', 'pk'
    )
    return render(request, 'team/roster.html', {
        'page_title': 'Class roster',
        'learners': learners,
        'stage': stage,
        'stage_choices': Registration.STAGE_CHOICES,
    })


@private_team_page
@transaction.atomic
@require_http_methods(['GET', 'POST'])
def roster_detail(request, pk):
    if not _can_view_roster(request):
        return _deny_or_login(request)
    learner = get_object_or_404(Registration, pk=pk)
    show_contact = False
    if request.method == 'POST':
        denied = _require_permission(request, 'core.reveal_contact')
        if denied:
            return denied
        show_contact = request.POST.get('reveal_contact') == 'true'
        if not show_contact:
            return _deny_or_login(request)
        record_audit_event(
            'contact_revealed',
            user=request.user,
            object_type='Registration',
            object_id=learner.pk,
            detail='Parent contact details revealed',
        )
    return render(request, 'team/roster_detail.html', {
        'page_title': 'Learner details',
        'learner': learner,
        'show_contact': show_contact,
        'can_reveal': _allowed(request, 'core.reveal_contact'),
        'phone_tel': _phone_tel(learner.parent_phone) if show_contact else '',
        'phone_whatsapp': _phone_whatsapp(learner.parent_phone) if show_contact else '',
    })
