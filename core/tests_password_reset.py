import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .models import AuditEvent
from .spam import team_password_reset_rate_limit_exceeded


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TeamPasswordResetTests(TestCase):
    password = 'A-long-team-password-782!'
    email = 'teammate@example.test'

    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='team-person',
            email=self.email,
            password=self.password,
            first_name='Team',
            last_name='Member',
        )
        self.user.groups.add(Group.objects.get_or_create(name='Facilitator')[0])

    def submit(self, email=None, **extra):
        request_extra = {}
        if 'REMOTE_ADDR' in extra:
            request_extra['REMOTE_ADDR'] = extra.pop('REMOTE_ADDR')
        data = {
            'email': email or self.email,
            'website': '',
            'form_timestamp': 'valid-for-test',
        }
        data.update(extra)
        with mock.patch('core.team_people.is_form_timestamp_valid', return_value=True):
            return self.client.post(
                reverse('team_password_reset_request'),
                data,
                **request_extra,
            )

    def send_reset_email(self, email=None):
        environment = {
            'BREVO_API_KEY': 'test-key',
            'CONTACT_FROM_EMAIL': 'website@example.test',
        }
        with mock.patch.dict(os.environ, environment):
            with mock.patch('core.notifications.urllib.request.urlopen') as send:
                response = self.submit(email)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(send.call_count, 1)
        payload = json.loads(send.call_args.args[0].data.decode('utf-8'))
        return response, payload

    def test_forgot_password_link_is_on_team_sign_in(self):
        response = self.client.get(reverse('team_login'))
        self.assertContains(response, reverse('team_password_reset_request'))
        self.assertContains(response, 'Forgot password?')

    def test_request_form_has_email_field_and_honeypot(self):
        response = self.client.get(reverse('team_password_reset_request'))
        self.assertContains(response, 'type="email"')
        self.assertContains(response, 'name="website"')
        self.assertContains(response, reverse('team_login'))

    def test_known_and_unknown_email_get_the_same_plain_message(self):
        known, _ = self.send_reset_email()
        with mock.patch('core.notifications.urllib.request.urlopen') as send:
            unknown = self.submit('unknown@example.test', REMOTE_ADDR='192.0.2.8')
        self.assertEqual(known.content, unknown.content)
        self.assertContains(
            known,
            'If that email belongs to a team account, we have sent a link to set a new password. Check your inbox and spam folder.',
        )
        send.assert_not_called()

    def test_email_contains_username_and_one_working_reset_link(self):
        _, payload = self.send_reset_email()
        self.assertEqual(payload['subject'], 'Reset your Mindset Coders team password')
        self.assertEqual(payload['to'], [{'email': self.email}])
        body = payload['textContent']
        self.assertIn('Your username is: team-person.', body)
        self.assertNotIn(self.email, body)
        self.assertNotIn('Team Member', body)
        self.assertEqual(body.count('http://testserver/'), 1)
        link = body.split(
            'Open this link to set a new password: ', 1
        )[1].split('. If you did not ask', 1)[0]
        path = urlsplit(link).path
        self.assertEqual(self.client.get(path).status_code, 200)
        response = self.client.post(path, {
            'new_password1': 'New!Password-785-Orbit',
            'new_password2': 'New!Password-785-Orbit',
        })
        self.assertRedirects(response, reverse('team_home'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New!Password-785-Orbit'))
        self.assertEqual(self.client.get(path).status_code, 400)

    def test_wrong_and_expired_links_show_a_friendly_error(self):
        _, payload = self.send_reset_email()
        link = payload['textContent'].split(
            'Open this link to set a new password: ', 1
        )[1].split('. If you did not ask', 1)[0]
        path = urlsplit(link).path
        self.assertEqual(self.client.get(path[:-2] + 'x/').status_code, 400)
        with mock.patch(
            'django.contrib.auth.tokens.PasswordResetTokenGenerator._now',
            return_value=datetime.now() + timedelta(days=4),
        ):
            expired = self.client.get(path)
        self.assertEqual(expired.status_code, 400)
        self.assertContains(
            expired,
            'This password reset link is no longer valid or has expired.',
            status_code=400,
        )

    def test_inactive_account_gets_same_message_and_no_email(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        with mock.patch('core.notifications.urllib.request.urlopen') as send:
            response = self.submit()
        self.assertContains(
            response,
            'If that email belongs to a team account, we have sent a link to set a new password. Check your inbox and spam folder.',
        )
        send.assert_not_called()

    def test_invalid_form_timestamp_returns_a_friendly_page(self):
        response = self.client.post(reverse('team_password_reset_request'), {
            'email': self.email,
            'form_timestamp': 'invalid',
            'website': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please check the form and try again.')

    def test_rate_limit_applies_per_visitor_and_email(self):
        factory = RequestFactory()
        for count in range(5):
            request = factory.post(
                '/', REMOTE_ADDR='198.51.100.20',
            )
            self.assertFalse(team_password_reset_rate_limit_exceeded(
                request, 'person{}@example.test'.format(count),
            ))
        self.assertTrue(team_password_reset_rate_limit_exceeded(
            factory.post('/', REMOTE_ADDR='198.51.100.20'),
            'different@example.test',
        ))

        cache.clear()
        for count in range(5):
            request = factory.post(
                '/', REMOTE_ADDR='192.0.2.{}'.format(count + 1),
            )
            self.assertFalse(team_password_reset_rate_limit_exceeded(
                request, 'same@example.test',
            ))
        self.assertTrue(team_password_reset_rate_limit_exceeded(
            factory.post('/', REMOTE_ADDR='192.0.2.9'),
            'same@example.test',
        ))

    def test_rate_limit_message_and_honeypot_suppress_email(self):
        request_factory = RequestFactory()
        for _ in range(5):
            team_password_reset_rate_limit_exceeded(
                request_factory.post('/', REMOTE_ADDR='203.0.113.20'),
                'other@example.test',
            )
        with mock.patch('core.notifications.urllib.request.urlopen') as send:
            response = self.submit(REMOTE_ADDR='203.0.113.20')
            honeypot = self.submit(
                'bot@example.test', website='filled', REMOTE_ADDR='203.0.113.21',
            )
        self.assertContains(response, 'Please wait a while before sending another message.')
        self.assertContains(
            honeypot,
            'If that email belongs to a team account, we have sent a link to set a new password.',
        )
        send.assert_not_called()

    def test_missing_brevo_settings_logs_warning_and_shows_same_message(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertLogs('core.notifications', level='WARNING'):
                response = self.submit()
        self.assertContains(
            response,
            'If that email belongs to a team account, we have sent a link to set a new password.',
        )

    def test_audit_events_contain_no_account_details(self):
        _, payload = self.send_reset_email()
        link = payload['textContent'].split(
            'Open this link to set a new password: ', 1
        )[1].split('. If you did not ask', 1)[0]
        path = urlsplit(link).path
        self.client.post(path, {
            'new_password1': 'New!Password-785-Orbit',
            'new_password2': 'New!Password-785-Orbit',
        })
        events = AuditEvent.objects.filter(
            action__in=(
                'password_reset_requested',
                'password_reset_completed',
            ),
        )
        self.assertEqual(events.count(), 2)
        for event in events:
            self.assertIsNone(event.user)
            self.assertEqual(event.username, '')
            self.assertEqual(event.object_id, '')
            self.assertNotIn(self.email, str(event))
            self.assertNotIn(self.user.username, str(event))
            self.assertNotIn('Team Member', event.detail)
