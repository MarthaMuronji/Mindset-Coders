import os
import tomllib
from pathlib import Path
from unittest import mock

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from django.test import SimpleTestCase, override_settings

from mindset_project import settings as project_settings


ROOT = Path(__file__).resolve().parent.parent


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


class DependencyManifestTests(SimpleTestCase):
    def test_pyproject_dependencies_match_requirements_txt(self):
        requirements_path = ROOT / 'requirements.txt'
        pyproject_path = ROOT / 'pyproject.toml'

        requirements = [
            Requirement(line.strip())
            for line in requirements_path.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.lstrip().startswith('#')
        ]
        pyproject = tomllib.loads(pyproject_path.read_text(encoding='utf-8'))
        dependencies = [
            Requirement(dependency)
            for dependency in pyproject['project']['dependencies']
        ]

        def dependency_map(items):
            return {
                canonicalize_name(item.name): (
                    str(item.specifier),
                    str(item.marker) if item.marker else None,
                )
                for item in items
            }

        requirements_map = dependency_map(requirements)
        pyproject_map = dependency_map(dependencies)
        package_names = sorted(set(requirements_map) | set(pyproject_map))
        differences = [
            f'{name}: requirements.txt={requirements_map.get(name)!r}, '
            f'pyproject.toml={pyproject_map.get(name)!r}'
            for name in package_names
            if requirements_map.get(name) != pyproject_map.get(name)
        ]

        self.assertFalse(
            differences,
            'Dependency manifests differ:\n' + '\n'.join(differences),
        )
