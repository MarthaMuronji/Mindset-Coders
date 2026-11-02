from functools import wraps
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods

from .models import ContactMessage, Registration


REGISTRATION_STATUSES = {
    'pending': 'Waiting for payment',
    'part_paid': 'Part paid',
    'paid': 'Paid',
    'cancelled': 'Cancelled',
}
REGISTRATION_FILTERS = ('pending', 'part_paid', 'paid', 'cancelled')
METHOD_FILTERS = ('online', 'cash')
FOLLOW_UP_FILTERS = ('no', 'yes', 'all')
REGISTRATION_ACTIONS = ('paid', 'part_paid', 'cancel')
ACTION_TITLES = {
    'paid': 'Mark as paid in full',
    'part_paid': 'Record part payment',
    'cancel': 'Cancel registration',
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


@method_decorator(private_team_page, name='dispatch')
class TeamLoginView(LoginView):
    template_name = 'team/login.html'
    authentication_form = TeamLoginForm
    redirect_authenticated_user = True
    next_page = reverse_lazy('team_home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Team sign in'
        return context


team_logout = private_team_page(
    LogoutView.as_view(next_page=reverse_lazy('team_login'))
)


@private_team_page
def team_home(request):
    if not request.user.is_authenticated:
        return redirect(_login_url(request.get_full_path()))
    can_view_registrations = _allowed(request, 'core.view_registration')
    can_view_messages = _allowed(request, 'core.view_contactmessage')
    if not can_view_registrations and not can_view_messages:
        return _deny_or_login(request)
    return render(request, 'team/home.html', {
        'page_title': 'Team home',
        'can_view_registrations': can_view_registrations,
        'can_view_messages': can_view_messages,
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
    denied = _require_permission(request, 'core.view_registration')
    if denied:
        return denied

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
    })


@private_team_page
@require_http_methods(['GET', 'POST'])
def registration_detail(request, pk):
    denied = _require_permission(request, 'core.view_registration')
    if denied:
        return denied
    registration = get_object_or_404(Registration, pk=pk)
    if request.method == 'POST':
        denied = _require_permission(request, 'core.change_registration')
        if denied:
            return denied
        registration.payment_note = request.POST.get('payment_note', '').strip()
        registration.save(update_fields=['payment_note'])
        messages.success(request, 'Internal note saved.')
        return redirect('team_registration_detail', pk=registration.pk)
    context = _registration_context(registration)
    context.update({
        'page_title': 'Registration details',
        'can_change': _allowed(request, 'core.change_registration'),
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
@require_POST
def registration_action(request, pk, action):
    denied = _require_permission(request, 'core.view_registration')
    if denied:
        return denied
    denied = _require_permission(request, 'core.change_registration')
    if denied:
        return denied
    if action not in REGISTRATION_ACTIONS:
        raise Http404
    registration = get_object_or_404(Registration, pk=pk)
    confirmed = request.POST.get('confirmed') == 'true'
    form = RegistrationActionForm(
        request.POST if confirmed else None,
        action=action,
        registration=registration,
    )
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
        else:
            registration.payment_status = 'cancelled'
            registration.paid_at = now
            registration.payment_recorded_by = request.user.get_username()
            registration.save(update_fields=[
                'payment_status', 'paid_at', 'payment_recorded_by',
            ])
            messages.success(request, 'Registration cancelled.')
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
@require_POST
def message_follow_up(request, pk):
    denied = _require_permission(request, 'core.view_contactmessage')
    if denied:
        return denied
    denied = _require_permission(request, 'core.change_contactmessage')
    if denied:
        return denied
    contact_message = get_object_or_404(ContactMessage, pk=pk)
    handled = request.POST.get('handled') == 'true'
    contact_message.handled = handled
    contact_message.save(update_fields=['handled'])
    messages.success(
        request,
        'Message marked as followed up.' if handled else 'Message marked as not followed up.',
    )
    return redirect('{}?{}'.format(
        reverse('team_messages'),
        urlencode({'follow_up': request.POST.get('follow_up', 'no')}),
    ))
