import importlib
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import clear_url_caches, reverse
from django.utils import timezone

from core.middleware import IDLE_SIGN_OUT_MESSAGE
from core.models import AuditEvent, LoginThrottle
from core.spam import _visitor_ip
from core.throttle import (
    _throttle_keys,
    locked_seconds,
    record_failure,
)


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class LoginThrottleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='team-member',
            password='Correct-password-123!',
        )

    def post_team_login(self, password, ip='192.0.2.10', username=None):
        return self.client.post(
            reverse('team_login'),
            {
                'username': username or self.user.username,
                'password': password,
            },
            REMOTE_ADDR=ip,
        )

    def test_sixth_team_attempt_is_blocked_even_with_correct_password(self):
        for _ in range(5):
            self.post_team_login('wrong-password')

        response = self.post_team_login('Correct-password-123!')

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Too many attempts. Please wait 30 seconds and try again.',
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(
            AuditEvent.objects.filter(action='login_locked').count(),
            1,
        )

    def test_lock_wait_doubles_and_caps_at_900_seconds(self):
        request = RequestFactory().post(
            '/team/login/',
            REMOTE_ADDR='192.0.2.11',
        )
        now = [timezone.now()]
        expected_waits = [30, 60, 120, 240, 480, 900, 900]

        with mock.patch('core.throttle.timezone.now', side_effect=lambda: now[0]):
            for _ in range(4):
                record_failure(request, self.user.username)
            for expected in expected_waits:
                record_failure(request, self.user.username)
                username_key, _ = _throttle_keys(request, self.user.username)
                row = LoginThrottle.objects.get(key=username_key)
                self.assertEqual(
                    (row.locked_until - now[0]).total_seconds(),
                    expected,
                )
                now[0] = row.locked_until

    def test_username_ip_lock_does_not_block_another_ip(self):
        for _ in range(5):
            self.post_team_login('wrong-password', ip='192.0.2.12')

        response = self.post_team_login(
            'Correct-password-123!',
            ip='192.0.2.13',
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_many_ips_do_not_create_a_username_only_lock(self):
        for last_octet in range(20, 25):
            for _ in range(5):
                self.post_team_login(
                    'wrong-password',
                    ip='192.0.2.{}'.format(last_octet),
                )

        response = self.post_team_login(
            'Correct-password-123!',
            ip='192.0.2.25',
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_ip_limit_blocks_at_twenty_failures(self):
        for number in range(20):
            self.post_team_login(
                'wrong-password',
                ip='192.0.2.30',
                username='unknown-{}'.format(number),
            )

        response = self.post_team_login(
            'Correct-password-123!',
            ip='192.0.2.30',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Too many attempts.')

    def test_successful_login_resets_only_username_and_ip_key(self):
        for _ in range(3):
            self.post_team_login('wrong-password', ip='192.0.2.31')
        request = RequestFactory().post(
            '/team/login/',
            REMOTE_ADDR='192.0.2.31',
        )
        username_key, ip_key = _throttle_keys(request, self.user.username)
        self.assertEqual(LoginThrottle.objects.get(key=username_key).failures, 3)
        self.assertEqual(LoginThrottle.objects.get(key=ip_key).failures, 3)

        self.post_team_login(
            'Correct-password-123!',
            ip='192.0.2.31',
        )

        self.assertFalse(LoginThrottle.objects.filter(key=username_key).exists())
        self.assertEqual(LoginThrottle.objects.get(key=ip_key).failures, 3)

    def test_unknown_username_has_same_failure_message_and_status(self):
        real_user_response = self.post_team_login('wrong-password')
        unknown_user_response = self.post_team_login(
            'wrong-password',
            ip='192.0.2.32',
            username='not-a-real-user',
        )

        self.assertEqual(
            real_user_response.status_code,
            unknown_user_response.status_code,
        )
        self.assertEqual(
            list(real_user_response.context['form'].non_field_errors()),
            list(unknown_user_response.context['form'].non_field_errors()),
        )

    def test_get_is_not_throttled(self):
        for _ in range(5):
            self.post_team_login('wrong-password', ip='192.0.2.33')

        response = self.client.get(
            reverse('team_login'),
            REMOTE_ADDR='192.0.2.33',
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Too many attempts.')

    def test_throttle_keys_are_hmacs_not_usernames_or_ips(self):
        address = '192.0.2.34'
        for _ in range(5):
            self.post_team_login('wrong-password', ip=address)

        keys = list(LoginThrottle.objects.values_list('key', flat=True))
        self.assertEqual(len(keys), 2)
        for key in keys:
            self.assertRegex(key, r'^[0-9a-f]{64}$')
            self.assertNotIn(self.user.username, key)
            self.assertNotIn(address, key)

    def test_stale_failure_window_restarts_at_zero(self):
        request = RequestFactory().post(
            '/team/login/',
            REMOTE_ADDR='192.0.2.35',
        )
        username_key, _ = _throttle_keys(request, self.user.username)
        row = LoginThrottle.objects.create(
            key=username_key,
            failures=4,
        )
        LoginThrottle.objects.filter(pk=row.pk).update(
            updated_at=timezone.now() - timedelta(hours=2),
        )

        record_failure(request, self.user.username)

        self.assertEqual(
            LoginThrottle.objects.get(key=username_key).failures,
            1,
        )

    def test_existing_ip_helper_is_used(self):
        request = RequestFactory().get(
            '/',
            REMOTE_ADDR='192.0.2.36',
        )
        self.assertEqual(_visitor_ip(request), '192.0.2.36')


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class LoginHardeningIntegrationTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username='site-admin',
            email='admin@example.test',
            password='Admin-password-123!',
        )

    def test_admin_login_is_throttled(self):
        for _ in range(5):
            self.client.post(
                '/admin/login/',
                {
                    'username': self.admin_user.username,
                    'password': 'wrong-password',
                },
                REMOTE_ADDR='192.0.2.40',
            )

        response = self.client.post(
            '/admin/login/',
            {
                'username': self.admin_user.username,
                'password': 'Admin-password-123!',
            },
            REMOTE_ADDR='192.0.2.40',
            follow=True,
        )

        self.assertContains(response, 'Too many attempts.')
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_idle_team_session_redirects_with_message_and_return_path(self):
        team_user = get_user_model().objects.create_user(
            username='team-user',
            password='Team-password-123!',
        )
        self.client.force_login(team_user)
        self.client.get('/team/')
        session = self.client.session
        session.set_expiry(-1)
        session.save()

        response = self.client.get('/team/registrations/?page=2', follow=True)

        self.assertEqual(response.redirect_chain[0][0], '/team/login/?next=%2Fteam%2Fregistrations%2F%3Fpage%3D2')
        self.assertContains(response, IDLE_SIGN_OUT_MESSAGE)

    @override_settings(DEBUG=False)
    def test_cookie_and_security_settings(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 7200)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(settings.X_FRAME_OPTIONS, 'DENY')
        self.assertEqual(settings.SECURE_REFERRER_POLICY, 'same-origin')
        self.assertEqual(getattr(settings, 'SECURE_HSTS_SECONDS', 0), 0)

    @override_settings(ADMIN_URL_PATH='private-admin-check-6721/')
    def test_private_admin_path_and_response_headers(self):
        import mindset_project.urls as project_urls

        original_patterns = project_urls.urlpatterns
        try:
            importlib.reload(project_urls)
            clear_url_caches()

            old_path_response = self.client.get('/admin/')
            new_path_response = self.client.get('/private-admin-check-6721/')
            robots_response = self.client.get('/robots.txt')

            self.assertEqual(old_path_response.status_code, 404)
            self.assertNotEqual(new_path_response.status_code, 404)
            self.assertEqual(
                new_path_response['X-Robots-Tag'],
                'noindex, nofollow',
            )
            self.assertIn('no-cache', new_path_response['Cache-Control'])
            self.assertNotContains(robots_response, 'private-admin-check-6721')
            self.assertContains(robots_response, 'Disallow: /admin/')
        finally:
            project_urls.urlpatterns = original_patterns
            clear_url_caches()
