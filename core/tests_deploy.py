import os
from unittest import mock

from django.test import SimpleTestCase, override_settings

from mindset_project import settings as project_settings


class AllowedHostsTests(SimpleTestCase):
    def test_vercel_host_is_accepted(self):
        response = self.client.get(
            '/',
            HTTP_HOST='mindset-coders.vercel.app',
        )

        self.assertEqual(response.status_code, 200)

    def test_render_host_is_still_accepted(self):
        response = self.client.get(
            '/',
            HTTP_HOST='mindset-coders.onrender.com',
        )

        self.assertEqual(response.status_code, 200)

    def test_unknown_host_is_refused(self):
        response = self.client.get(
            '/',
            HTTP_HOST='unknown.example.invalid',
        )

        self.assertEqual(response.status_code, 400)

    def test_extra_allowed_hosts_environment_variable_is_honored(self):
        with mock.patch.dict(
            os.environ,
            {'EXTRA_ALLOWED_HOSTS': 'extra.example, another.example'},
        ):
            allowed_hosts = project_settings._get_allowed_hosts()

        with override_settings(ALLOWED_HOSTS=allowed_hosts):
            response = self.client.get('/', HTTP_HOST='extra.example')

        self.assertEqual(response.status_code, 200)
