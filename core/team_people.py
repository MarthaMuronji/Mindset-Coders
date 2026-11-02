import binascii

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from .audit import record_audit_event
from .models import AuditEvent
from .team import (
    _allowed,
    _deny_or_login,
    _phone_tel,
    _phone_whatsapp,
    _require_permission,
    private_team_page,
)


TEAM_ROLES = {
    'Owner': (
        'registration.view_full_registration',
        'registration.view_finance_fields',
        'registration.view_roster',
        'registration.reveal_contact',
        'registration.record_payment',
        'registration.anonymise_registration',
        'registration.view_registration',
        'registration.change_registration',
        'contactmessage.view_contactmessage',
        'contactmessage.change_contactmessage',
        'auditevent.manage_team',
        'auditevent.view_audit_log',
    ),
    'Registrations officer': (
        'registration.view_full_registration',
        'registration.record_payment',
        'contactmessage.view_contactmessage',
        'contactmessage.change_contactmessage',
    ),
    'Finance': (
        'registration.view_finance_fields',
        'registration.record_payment',
    ),
    'Facilitator': (
        'registration.view_roster',
        'registration.reveal_contact',
    ),
    'Communications': (
        'contactmessage.view_contactmessage',
        'contactmessage.change_contactmessage',
    ),
}

ROLE_CHOICES = tuple((name, name) for name in TEAM_ROLES)


def sync_team_roles(using='default', app_config=None, apps=None):
    from django.contrib.auth.management import create_permissions
    from django.contrib.auth.models import Group, Permission

    if app_config is not None:
        create_permissions(
            app_config,
            verbosity=0,
            interactive=False,
            using=using,
            apps=apps,
        )

    for role, permission_labels in TEAM_ROLES.items():
        group, _created = Group.objects.using(using).get_or_create(name=role)
        permissions = []
        for label in permission_labels:
            model_name, codename = label.split('.', 1)
            permission = Permission.objects.using(using).get(
                content_type__app_label='core',
                content_type__model=model_name,
                codename=codename,
            )
            permissions.append(permission.pk)
        group.permissions.set(permissions)


def _set_team_role(user, role):
    from django.contrib.auth.models import Group

    if role and role not in TEAM_ROLES:
        raise forms.ValidationError('Choose one of the listed team roles.')
    groups = list(Group.objects.filter(name__in=TEAM_ROLES))
    user.groups.remove(*groups)
    if user.is_staff or user.is_superuser:
        user.is_staff = False
        user.is_superuser = False
        user.save(update_fields=['is_staff', 'is_superuser'])
    if role:
        user.groups.add(Group.objects.get(name=role))


def _current_team_role(user):
    roles = list(user.groups.filter(name__in=TEAM_ROLES).values_list('name', flat=True))
    return roles[0] if len(roles) == 1 else ''


def _make_username(email):
    User = get_user_model()
    field = User.USERNAME_FIELD
    if field == 'email':
        return email
    local_part = email.split('@', 1)[0]
    base = ''.join(character for character in local_part.lower() if character.isalnum() or character in '._-')
    base = base.strip('._-') or 'team'
    max_length = User._meta.get_field(field).max_length or 150
    base = base[:max_length]
    username = base
    suffix = 1
    while User._default_manager.filter(**{field: username}).exists():
        suffix_text = str(suffix)
        username = '{}{}'.format(base[:max_length - len(suffix_text)], suffix_text)
        suffix += 1
    return username


def create_team_invitee(full_name, email, role, actor=None, audit_username=None):
    validate_email(email)
    if role not in TEAM_ROLES:
        raise forms.ValidationError('Choose one of the listed team roles.')
    User = get_user_model()
    if User._default_manager.filter(email__iexact=email).exists():
        raise forms.ValidationError('A person with this email address already exists.')
    first_name, _, last_name = full_name.strip().partition(' ')
    with transaction.atomic():
        user = User._default_manager.create_user(
            **{
                User.USERNAME_FIELD: _make_username(email),
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
            }
        )
        user.set_unusable_password()
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.save(update_fields=['password', 'is_active', 'is_staff', 'is_superuser'])
        _set_team_role(user, role)
        record_audit_event(
            'invite_sent',
            user=actor,
            object_type='User',
            object_id=user.pk,
            detail='Invitation link created',
            username=audit_username,
        )
    return user


def invite_path(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return reverse('team_welcome', kwargs={'uidb64': uid, 'token': token})


def _team_user_queryset():
    User = get_user_model()
    return User._default_manager.filter(
        groups__name__in=TEAM_ROLES,
    ).distinct().order_by('first_name', 'last_name', User.USERNAME_FIELD)


class InviteForm(forms.Form):
    full_name = forms.CharField(max_length=150, label='Full name')
    email = forms.EmailField()
    role = forms.ChoiceField(choices=ROLE_CHOICES)

    def clean_email(self):
        email = self.cleaned_data['email']
        User = get_user_model()
        if User._default_manager.filter(email__iexact=email).exists():
            raise forms.ValidationError('A person with this email address already exists.')
        return email


class TeamPeopleActionForm(forms.Form):
    action = forms.ChoiceField(choices=(
        ('role', 'Change role'),
        ('off', 'Switch off'),
        ('on', 'Switch back on'),
        ('invite', 'Make a new invite link'),
    ))
    user_id = forms.IntegerField(min_value=1)
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=False)


@private_team_page
def people_list(request):
    denied = _require_permission(request, 'core.manage_team')
    if denied:
        return denied
    form = InviteForm()
    action_form = TeamPeopleActionForm()
    invite_url = request.session.pop('team_invite_url', '')
    if request.method == 'POST':
        if request.POST.get('form_type') == 'invite':
            form = InviteForm(request.POST)
            if form.is_valid():
                user = create_team_invitee(
                    form.cleaned_data['full_name'],
                    form.cleaned_data['email'],
                    form.cleaned_data['role'],
                    actor=request.user,
                )
                path = invite_path(user)
                invite_url = request.build_absolute_uri(path)
                request.session['team_invite_url'] = invite_url
                from .notifications import send_team_invite

                send_team_invite(user.email, invite_url)
                messages.success(request, 'Invitation link created. Copy it and send it to the new team member.')
                return redirect('team_people')
        else:
            action_form = TeamPeopleActionForm(request.POST)
            if action_form.is_valid():
                person = get_object_or_404(
                    _team_user_queryset(),
                    pk=action_form.cleaned_data['user_id'],
                )
                action = action_form.cleaned_data['action']
                if action == 'role':
                    role = action_form.cleaned_data['role']
                    if not role:
                        action_form.add_error('role', 'Choose a role.')
                    elif person.pk == request.user.pk and _current_team_role(person) == 'Owner' and role != 'Owner':
                        action_form.add_error(None, 'You cannot remove your own Owner role.')
                    else:
                        previous_role = _current_team_role(person)
                        with transaction.atomic():
                            _set_team_role(person, role)
                            if previous_role != role:
                                record_audit_event(
                                    'role_changed',
                                    user=request.user,
                                    object_type='User',
                                    object_id=person.pk,
                                    detail='Team role changed',
                                )
                        if previous_role != role:
                            messages.success(request, 'Team role updated.')
                            return redirect('team_people')
                elif action == 'off':
                    if person.pk == request.user.pk:
                        action_form.add_error(None, 'You cannot switch off your own account.')
                    elif person.is_active:
                        with transaction.atomic():
                            person.is_active = False
                            person.save(update_fields=['is_active'])
                            record_audit_event(
                                'person_switched_off',
                                user=request.user,
                                object_type='User',
                                object_id=person.pk,
                                detail='Team member switched off',
                            )
                        messages.success(request, 'Team member switched off.')
                        return redirect('team_people')
                elif action == 'on':
                    if not person.is_active:
                        with transaction.atomic():
                            person.is_active = True
                            person.save(update_fields=['is_active'])
                            record_audit_event(
                                'person_switched_on',
                                user=request.user,
                                object_type='User',
                                object_id=person.pk,
                                detail='Team member switched on',
                            )
                        messages.success(request, 'Team member switched on.')
                        return redirect('team_people')
                else:
                    if not person.is_active:
                        action_form.add_error(None, 'Switch this account back on before making a new invite link.')
                    else:
                        with transaction.atomic():
                            person.set_unusable_password()
                            person.save(update_fields=['password'])
                            invite_url = request.build_absolute_uri(invite_path(person))
                            record_audit_event(
                                'invite_sent',
                                user=request.user,
                                object_type='User',
                                object_id=person.pk,
                                detail='Invitation link created',
                            )
                        request.session['team_invite_url'] = invite_url
                        from .notifications import send_team_invite

                        send_team_invite(person.email, invite_url)
                        messages.success(request, 'A new invitation link was created.')
                        return redirect('team_people')
    people = list(_team_user_queryset())
    for person in people:
        person.team_role = _current_team_role(person)
    return render(request, 'team/people.html', {
        'page_title': 'People',
        'people': people,
        'invite_form': form,
        'action_form': action_form,
        'invite_url': invite_url,
        'roles': ROLE_CHOICES,
    })


def _get_invited_user(uidb64):
    User = get_user_model()
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        return User._default_manager.get(pk=user_id)
    except (binascii.Error, TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


@private_team_page
def team_welcome(request, uidb64, token):
    user = _get_invited_user(uidb64)
    if user is None or not user.is_active or user.has_usable_password():
        return render(request, 'team/welcome_invalid.html', {
            'page_title': 'Invite link unavailable',
        }, status=400)
    if not default_token_generator.check_token(user, token):
        return render(request, 'team/welcome_invalid.html', {
            'page_title': 'Invite link unavailable',
        }, status=400)
    form = SetPasswordForm(user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        auth_login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
        record_audit_event(
            'sign_in',
            user=user,
            object_type='User',
            object_id=user.pk,
            detail='Signed in through team invitation',
        )
        return redirect('team_home')
    return render(request, 'team/welcome.html', {
        'page_title': 'Set your password',
        'form': form,
    })


class AuditFilterForm(forms.Form):
    person = forms.ChoiceField(required=False)
    action = forms.ChoiceField(required=False)
    start_date = forms.DateField(required=False, input_formats=('%Y-%m-%d',))
    end_date = forms.DateField(required=False, input_formats=('%Y-%m-%d',))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usernames = AuditEvent.objects.order_by().values_list('username', flat=True).distinct()
        self.fields['person'].choices = [('', 'All people')] + [
            (username, username) for username in usernames if username
        ]
        self.fields['action'].choices = [('', 'All actions')] + list(AuditEvent.ACTION_CHOICES)


@private_team_page
def audit_log(request):
    denied = _require_permission(request, 'core.view_audit_log')
    if denied:
        return denied
    form = AuditFilterForm(request.GET or None)
    events = AuditEvent.objects.select_related('user').order_by('-created_at', '-pk')
    if form.is_valid():
        data = form.cleaned_data
        if data['person']:
            events = events.filter(username=data['person'])
        if data['action']:
            events = events.filter(action=data['action'])
        if data['start_date']:
            events = events.filter(created_at__date__gte=data['start_date'])
        if data['end_date']:
            events = events.filter(created_at__date__lte=data['end_date'])
    page = Paginator(events, 50).get_page(request.GET.get('page'))
    previous_params = request.GET.copy()
    next_params = request.GET.copy()
    previous_params['page'] = page.previous_page_number() if page.has_previous() else 1
    next_params['page'] = page.next_page_number() if page.has_next() else page.number
    return render(request, 'team/audit.html', {
        'page_title': 'Activity log',
        'filter_form': form,
        'events': page,
        'previous_query': previous_params.urlencode(),
        'next_query': next_params.urlencode(),
    })


def create_command_invitee(full_name, email, role):
    user = create_team_invitee(
        full_name,
        email,
        role,
        audit_username='management command',
    )
    path = invite_path(user)
    return user, path
