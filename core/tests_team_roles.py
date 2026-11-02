import json
import os
from datetime import datetime, timedelta
from io import StringIO
from unittest import mock
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse, resolve

from .models import AuditEvent, ContactMessage, Registration
from .team_people import TEAM_ROLES, invite_path


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TeamRolesTests(TestCase):
    password = 'A-long-team-password-782!'

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username='team-owner',
            email='owner@example.test',
            password=self.password,
            first_name='Team',
            last_name='Owner',
        )
        self.add_role(self.owner, 'Owner')
        self.registration = Registration.objects.create(
            parent_name='Secret Parent Name',
            parent_email='secret-parent@example.test',
            parent_phone='+256 700 111222',
            learner_name='Secret Learner Name',
            learner_age=987,
            school_name='Secret School Name',
            programme='holiday',
            stage='build',
            payment_method='cash',
            payment_status='pending',
            amount_due=400000,
            amount_paid=100000,
            receipt_number='PRIVATE-RECEIPT',
            payment_note='PRIVATE-NOTE',
            consent=True,
        )
        self.contact = ContactMessage.objects.create(
            name='Message Parent',
            email='message-parent@example.test',
            phone='0700123456',
            role='parent',
            message='Please contact me.',
        )

    @staticmethod
    def add_role(user, role):
        user.groups.add(Group.objects.get(name=role))

    def make_role_user(self, role):
        User = get_user_model()
        user = User.objects.create_user(
            username=role.lower().replace(' ', '-'),
            email='{}@example.test'.format(role.lower().replace(' ', '-')),
            password=self.password,
        )
        self.add_role(user, role)
        return user

    def client_for(self, role):
        from django.test import Client

        client = Client()
        client.force_login(self.make_role_user(role))
        return client

    def test_role_access_matrix(self):
        urls = {
            'registrations': reverse('team_registrations'),
            'detail': reverse(
                'team_registration_detail',
                kwargs={'pk': self.registration.pk},
            ),
            'roster': reverse('team_roster'),
            'messages': reverse('team_messages'),
            'people': reverse('team_people'),
            'audit': reverse('team_audit'),
        }
        expected = {
            'Owner': (200, 200, 200, 200, 200, 200),
            'Registrations officer': (200, 200, 200, 200, 403, 403),
            'Finance': (200, 200, 403, 403, 403, 403),
            'Facilitator': (403, 403, 200, 403, 403, 403),
            'Communications': (403, 403, 403, 200, 403, 403),
        }
        for role, expected_codes in expected.items():
            client = self.client_for(role)
            actual_codes = tuple(
                client.get(url).status_code for url in urls.values()
            )
            with self.subTest(role=role):
                self.assertEqual(actual_codes, expected_codes)

    def test_finance_detail_and_list_hide_unapproved_fields(self):
        client = self.client_for('Finance')
        detail = client.get(reverse(
            'team_registration_detail',
            kwargs={'pk': self.registration.pk},
        ))
        self.assertContains(detail, 'Secret Learner Name')
        self.assertContains(detail, 'Secret Parent Name')
        self.assertContains(detail, 'PRIVATE-RECEIPT')
        self.assertContains(detail, 'PRIVATE-NOTE')
        for hidden in (
            '987',
            'Secret School Name',
            'secret-parent@example.test',
        ):
            with self.subTest(hidden=hidden):
                self.assertNotContains(detail, hidden)
        listing = client.get(reverse('team_registrations'))
        self.assertContains(listing, 'Secret Learner Name')
        self.assertNotContains(listing, 'Secret Parent Name')
        self.assertNotContains(listing, 'PRIVATE-RECEIPT')

    def test_facilitator_cannot_reach_registration_or_payment_actions(self):
        client = self.client_for('Facilitator')
        action_url = reverse(
            'team_registration_action',
            kwargs={'pk': self.registration.pk, 'action': 'paid'},
        )
        self.assertEqual(client.post(action_url).status_code, 403)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.payment_status, 'pending')

    def test_finance_can_record_payment_and_audit_the_payment_and_status(self):
        client = self.client_for('Finance')
        action_url = reverse(
            'team_registration_action',
            kwargs={'pk': self.registration.pk, 'action': 'paid'},
        )
        self.assertEqual(client.post(action_url).status_code, 200)
        response = client.post(action_url, {
            'confirmed': 'true',
            'amount': '300000',
            'receipt_number': 'PAID-1',
        })
        self.assertEqual(response.status_code, 302)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.payment_status, 'paid')
        self.assertEqual(self.registration.amount_paid, 400000)
        self.assertEqual(
            self.registration.payment_recorded_by,
            get_user_model().objects.get(
                pk=client.session['_auth_user_id']
            ).username,
        )
        self.assertEqual(
            AuditEvent.objects.filter(action='payment_recorded').count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(action='status_changed').count(),
            1,
        )

    def test_communications_cannot_open_registrations(self):
        client = self.client_for('Communications')
        self.assertEqual(client.get(reverse('team_registrations')).status_code, 403)
        self.assertEqual(
            client.get(reverse(
                'team_registration_detail',
                kwargs={'pk': self.registration.pk},
            )).status_code,
            403,
        )

    def test_roster_reveal_shows_contact_and_writes_one_audit_event(self):
        client = self.client_for('Facilitator')
        url = reverse('team_roster_detail', kwargs={'pk': self.registration.pk})
        response = client.get(url)
        self.assertContains(response, 'Secret Learner Name')
        self.assertContains(response, '987')
        self.assertNotContains(response, 'Secret Parent Name')
        self.assertNotContains(response, '+256 700 111222')
        self.assertNotContains(response, 'secret-parent@example.test')
        response = client.post(url, {'reveal_contact': 'true'})
        self.assertContains(response, 'Secret Parent Name')
        self.assertContains(response, '+256 700 111222')
        self.assertContains(response, 'wa.me/256700111222')
        self.assertNotContains(response, 'secret-parent@example.test')
        self.assertEqual(
            AuditEvent.objects.filter(action='contact_revealed').count(),
            1,
        )

    def test_reveal_requires_permission_and_post(self):
        client = self.client_for('Registrations officer')
        url = reverse('team_roster_detail', kwargs={'pk': self.registration.pk})
        self.assertEqual(client.post(url, {'reveal_contact': 'true'}).status_code, 403)

    def test_people_page_requires_manage_team_permission(self):
        self.assertEqual(
            self.client_for('Finance').get(reverse('team_people')).status_code,
            403,
        )
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('team_people')).status_code, 200)

    def test_invite_creates_unusable_password_non_staff_user_and_welcome_is_one_time(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('team_people'), {
            'form_type': 'invite',
            'full_name': 'New Teammate',
            'email': 'new-teammate@example.test',
            'role': 'Facilitator',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('team_people'))
        person = get_user_model().objects.get(email='new-teammate@example.test')
        self.assertFalse(person.has_usable_password())
        self.assertTrue(person.is_active)
        self.assertFalse(person.is_staff)
        self.assertFalse(person.is_superuser)
        self.assertEqual(list(person.groups.values_list('name', flat=True)), ['Facilitator'])
        page = self.client.get(reverse('team_people'))
        self.assertContains(page, 'team/welcome/')
        path = urlsplit(page.context['invite_url']).path
        welcome = self.client.get(path)
        self.assertContains(welcome, 'Set your password')
        response = self.client.post(path, {
            'new_password1': 'Bamboo!Orbit$Plane938',
            'new_password2': 'Bamboo!Orbit$Plane938',
        })
        self.assertRedirects(response, reverse('team_home'))
        person.refresh_from_db()
        self.assertTrue(person.has_usable_password())
        self.assertEqual(self.client.get(path).status_code, 400)

    def test_tampered_and_expired_invite_links_fail(self):
        person = get_user_model().objects.create_user(
            username='invitee',
            email='invitee@example.test',
        )
        self.add_role(person, 'Facilitator')
        path = invite_path(person)
        uid, token = path.strip('/').split('/')[-2:]
        client = self.client
        self.assertEqual(
            client.get(reverse(
                'team_welcome',
                kwargs={'uidb64': uid, 'token': token[:-1] + 'x'},
            )).status_code,
            400,
        )
        with mock.patch(
            'django.contrib.auth.tokens.PasswordResetTokenGenerator._now',
            return_value=datetime.now() + timedelta(days=4),
        ):
            self.assertEqual(client.get(path).status_code, 400)

    def test_switching_person_off_blocks_their_next_request(self):
        person = self.make_role_user('Facilitator')
        from django.test import Client

        person_client = Client()
        person_client.force_login(person)
        self.client.force_login(self.owner)
        response = self.client.post(reverse('team_people'), {
            'form_type': 'action',
            'action': 'off',
            'user_id': person.pk,
        })
        self.assertRedirects(response, reverse('team_people'))
        response = person_client.get(reverse('team_roster'))
        self.assertRedirects(
            response,
            '{}?next={}'.format(reverse('team_login'), reverse('team_roster')),
        )

    def test_owner_cannot_demote_or_deactivate_themselves(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('team_people'), {
            'form_type': 'action',
            'action': 'role',
            'user_id': self.owner.pk,
            'role': 'Finance',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.owner.groups.filter(name='Owner').exists())
        response = self.client.post(reverse('team_people'), {
            'form_type': 'action',
            'action': 'off',
            'user_id': self.owner.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_role_change_is_recorded_without_personal_details(self):
        person = self.make_role_user('Communications')
        self.client.force_login(self.owner)
        response = self.client.post(reverse('team_people'), {
            'form_type': 'action',
            'action': 'role',
            'user_id': person.pk,
            'role': 'Finance',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(person.groups.values_list('name', flat=True)), ['Finance'])
        event = AuditEvent.objects.get(action='role_changed')
        self.assertEqual(event.object_id, str(person.pk))
        self.assertNotIn(person.email, event.detail)

    def test_contact_follow_up_is_recorded(self):
        client = self.client_for('Communications')
        response = client.post(
            reverse('team_message_follow_up', kwargs={'pk': self.contact.pk}),
            {'handled': 'true', 'follow_up': 'no'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AuditEvent.objects.filter(
            action='message_followed_up',
            object_id=str(self.contact.pk),
        ).exists())

    def test_audit_events_never_store_learner_or_parent_contact_details(self):
        self.client.force_login(self.owner)
        self.client.get(reverse(
            'team_registration_detail',
            kwargs={'pk': self.registration.pk},
        ))
        self.client.post(
            reverse('team_roster_detail', kwargs={'pk': self.registration.pk}),
            {'reveal_contact': 'true'},
        )
        audit_page = self.client.get(reverse('team_audit'))
        self.assertContains(audit_page, 'Revealed parent contact')
        for event in AuditEvent.objects.all():
            values = '{} {} {} {}'.format(
                event.username,
                event.object_type,
                event.object_id,
                event.detail,
            )
            for private_value in (
                'Secret Learner Name',
                'Secret Parent Name',
                '+256 700 111222',
                'secret-parent@example.test',
            ):
                self.assertNotIn(private_value, values)

    def test_anonymise_removes_personal_fields_and_keeps_payment_data(self):
        self.client.force_login(self.owner)
        action = reverse(
            'team_registration_action',
            kwargs={'pk': self.registration.pk, 'action': 'anonymise'},
        )
        confirmation = self.client.post(action)
        self.assertContains(confirmation, 'This cannot be undone')
        response = self.client.post(action, {'confirmed': 'true'})
        self.assertRedirects(
            response,
            reverse('team_registration_detail', kwargs={'pk': self.registration.pk}),
        )
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.learner_name, 'Removed')
        self.assertEqual(self.registration.parent_name, 'Removed')
        self.assertEqual(self.registration.parent_email, 'Removed')
        self.assertEqual(self.registration.parent_phone, 'Removed')
        self.assertEqual(self.registration.school_name, '')
        self.assertEqual(self.registration.stage, 'build')
        self.assertEqual(self.registration.payment_status, 'pending')
        self.assertEqual(self.registration.amount_due, 400000)
        self.assertEqual(self.registration.amount_paid, 100000)
        self.assertEqual(self.registration.receipt_number, 'PRIVATE-RECEIPT')
        self.assertTrue(AuditEvent.objects.filter(action='anonymised').exists())

    def test_role_groups_have_exactly_the_required_permissions(self):
        for role, permission_labels in TEAM_ROLES.items():
            group = Group.objects.get(name=role)
            actual = {
                '{}.{}'.format(permission.content_type.model, permission.codename)
                for permission in group.permissions.select_related('content_type')
            }
            with self.subTest(role=role):
                self.assertSetEqual(actual, set(permission_labels))

    def test_management_command_prints_a_working_invitation_path(self):
        output = StringIO()
        call_command(
            'team_invite',
            'Command Owner',
            'command-owner@example.test',
            'Owner',
            stdout=output,
        )
        path = output.getvalue().strip()
        self.assertTrue(path.startswith('/team/welcome/'))
        self.assertEqual(resolve(path).url_name, 'team_welcome')
        person = get_user_model().objects.get(email='command-owner@example.test')
        self.assertFalse(person.has_usable_password())
        self.assertFalse(person.is_staff)
        self.assertTrue(AuditEvent.objects.filter(
            action='invite_sent',
            object_id=str(person.pk),
        ).exists())

    def test_audit_filters_and_pagination(self):
        self.client.force_login(self.owner)
        for index in range(55):
            AuditEvent.objects.create(
                username='filter-person' if index == 0 else 'another-person',
                action='sign_in' if index == 0 else 'failed_sign_in',
                object_type='User',
                object_id=str(index),
            )
        response = self.client.get(reverse('team_audit'), {
            'person': 'filter-person',
            'action': 'sign_in',
        })
        self.assertEqual(response.context['events'].paginator.count, 1)
        response = self.client.get(reverse('team_audit'))
        self.assertEqual(len(response.context['events']), 50)
        self.assertContains(response, 'Next')

    def test_private_team_pages_keep_noindex_no_cache_and_no_public_links(self):
        self.client.force_login(self.owner)
        urls = (
            reverse('team_roster'),
            reverse('team_roster_detail', kwargs={'pk': self.registration.pk}),
            reverse('team_people'),
            reverse('team_audit'),
        )
        for url in urls:
            response = self.client.get(url)
            with self.subTest(url=url):
                self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
                self.assertIn('no-store', response['Cache-Control'])
                self.assertContains(response, '<meta name="robots" content="noindex, nofollow">')
                self.assertNotContains(response, 'umami')
        public = self.client.get('/')
        self.assertNotContains(public, 'href="/team/')


class TeamInviteEmailTests(TestCase):
    def test_invite_email_contains_only_short_text_and_invite_link(self):
        from .notifications import send_team_invite

        environment = {
            'BREVO_API_KEY': 'test-key',
            'CONTACT_FROM_EMAIL': 'team@example.test',
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            with mock.patch('core.notifications.urllib.request.urlopen') as send:
                send.return_value.read.return_value = b''
                send.return_value.close.return_value = None
                self.assertTrue(send_team_invite(
                    'person@example.test',
                    'https://example.test/team/welcome/example/token/',
                ))
        payload = json.loads(send.call_args.args[0].data.decode('utf-8'))
        self.assertIn('https://example.test/team/welcome/example/token/', payload['textContent'])
        self.assertNotIn('Learner', payload['textContent'])
        self.assertNotIn('Parent', payload['textContent'])
