import csv
import html
import time
from io import StringIO
from unittest import mock
from urllib.parse import parse_qs, unquote, urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.signing import TimestampSigner
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from . import views
from .models import AuditEvent, CareerRoleState, JobApplication
from .spam import FORM_TIMESTAMP_SALT
from .sitemaps import StaticViewSitemap


class CareersPageTests(TestCase):
    def test_careers_page_renders_and_returns_200(self):
        response = self.client.get(reverse('careers'))
        self.assertEqual(response.status_code, 200)

    def test_page_is_public_when_steam_experience_is_not_public(self):
        with override_settings(STEAM_EXPERIENCE_PUBLIC=False):
            response = self.client.get(reverse('careers'))
            self.assertEqual(response.status_code, 200)
            self.assertIn('careers', StaticViewSitemap().items())

    def test_seo_meta_tags_and_page_title(self):
        response = self.client.get(reverse('careers'))
        self.assertContains(
            response,
            '<title>Careers | Mindset Coders Uganda</title>',
        )
        self.assertContains(
            response,
            '<meta name="description" content="Open roles at Mindset Coders Uganda: Associate STEM Instructors and Junior Associate, Marketing &amp; Communications.">',
        )
        self.assertContains(
            response,
            '<meta property="og:title" content="Careers | Mindset Coders Uganda">',
        )
        self.assertContains(
            response,
            '<meta property="og:description" content="Open roles at Mindset Coders Uganda: Associate STEM Instructors and Junior Associate, Marketing &amp; Communications.">',
        )
        self.assertContains(
            response,
            '<link rel="canonical" href="http://testserver/careers/">',
        )

    def test_both_roles_appear_and_hero_banner(self):
        response = self.client.get(reverse('careers'))

        # Hero badge, heading, circuit SVG
        self.assertContains(response, '<span class="badge">Careers</span>')
        self.assertContains(response, '<h1>We are hiring!</h1>')
        self.assertContains(response, 'careers-hero-circuit')

        # Role 1: Associate STEM Instructors
        self.assertContains(response, 'Associate STEM Instructors')
        self.assertContains(response, 'Part-Time')
        self.assertContains(response, 'Entry-Level')
        self.assertContains(response, 'Kampala')
        self.assertContains(
            response,
            'Mindset Coders is expanding its team of instructors passionate about technology, education and inspiring the next generation of innovators.',
        )

        # Role 2: Junior Associate, Marketing & Communications
        self.assertContains(response, 'Junior Associate, Marketing &amp; Communications')
        self.assertContains(response, 'Full-Time')
        self.assertContains(response, 'Early Career')
        self.assertContains(
            response,
            'Are you creative, curious and passionate about digital marketing, technology and storytelling?',
        )

    def test_each_apply_link_points_to_form_with_right_role(self):
        response = self.client.get(reverse('careers'))

        # Role 1 Apply link
        self.assertContains(
            response,
            'href="/careers/apply/?role=Associate%20STEM%20Instructors"',
        )
        self.assertContains(response, 'data-umami-event="apply-instructor"')

        # Role 2 Apply link
        self.assertContains(
            response,
            'href="/careers/apply/?role=Junior%20Associate%2C%20Marketing%20%26%20Communications"',
        )
        self.assertContains(response, 'data-umami-event="apply-marketing"')
        self.assertContains(response, 'data-umami-event-from="careers"')
        self.assertContains(response, 'Apply')

    def test_details_content_for_both_roles_is_present(self):
        response = self.client.get(reverse('careers'))

        # Native details and summary controls
        self.assertContains(response, '<details class="careers-details">')
        self.assertContains(response, '<summary class="careers-summary">')
        self.assertContains(response, 'View details')

        # Both roles are closed by default (no open attribute on details)
        self.assertNotContains(response, '<details class="careers-details" open>')

        # Role 1 details content
        self.assertContains(
            response,
            'We are looking for enthusiastic, reliable and curious individuals interested in teaching children and young people in the following areas:',
        )
        for card_title in (
            'Coding and software programming',
            'Robotics and electronics',
            'Foundational STEM education',
            'Design thinking and innovation',
        ):
            self.assertContains(response, card_title)

        for item in (
            'Recent graduates and early-career professionals in STEM, computer science, engineering, IT, education or related fields.',
            'Individuals with practical technical skills and a willingness to learn.',
            'Individuals who enjoy working with children and young people.',
            'Reliable, punctual and proactive individuals with strong communication skills.',
            'Individuals available for scheduled weekday and/or weekend teaching assignments.',
        ):
            self.assertContains(response, item)

        self.assertContains(
            response,
            'Previous teaching experience is an advantage but is not mandatory.',
        )

        for item in (
            'Instructor training and professional development.',
            'Access to structured curricula and teaching resources.',
            'Practical experience delivering STEM education programmes.',
            'Paid teaching assignments.',
            'Opportunities for professional growth within Mindset Coders.',
        ):
            self.assertContains(response, item)

        self.assertContains(
            response,
            'This is a part-time, assignment-based opportunity for individuals who are committed to learning, delivering quality work and growing with an ambitious education technology company.',
        )
        self.assertContains(response, 'Location: Kampala, Uganda')

        # Role 2 details content
        self.assertContains(
            response,
            'Mindset Coders is looking for a proactive individual to help us grow our brand, market our products and tell the stories behind our work in STEM education.',
        )
        self.assertContains(response, '<h2>What you will do</h2>')
        for item in (
            'Create engaging digital content, including graphics, photos and videos.',
            'Manage our social media platforms.',
            'Plan and execute marketing campaigns.',
            'Promote our products, programmes and events.',
            'Support lead generation and track marketing performance.',
        ):
            self.assertContains(response, item)

        for item in (
            'Recent graduates and early-career professionals in Marketing, Communications, Multimedia, Business or related fields.',
            'Creative individuals with practical content creation and video editing skills.',
            'Individuals familiar with social media platforms and digital marketing tools.',
            'Strong communicators who are proactive, organised, reliable and willing to learn.',
        ):
            self.assertContains(response, item)

        self.assertContains(
            response,
            'A strong portfolio and practical skills are highly valued.',
        )
        self.assertContains(response, 'Location: Kyanja, Kampala')

    def test_how_to_apply_box_removed_and_fallback_line_present(self):
        response = self.client.get(reverse('careers'))

        # Old long box is removed
        self.assertNotContains(response, '<h2>How to apply</h2>')
        self.assertNotContains(response, 'Subject: Associate STEM Instructor Application')
        self.assertNotContains(response, 'Subject: Marketing & Communications Associate Application')
        self.assertNotContains(response, 'Mindset Coders | BIG IDEAS START HERE')

        # Fallback short line with plain text email
        self.assertContains(response, 'info@mindset-group.org')
        self.assertNotContains(response, 'href="mailto:info@mindset-group.org"')

    def test_role_anchors_and_apply_anchor_exist(self):
        response = self.client.get(reverse('careers'))
        self.assertContains(response, 'id="associate-stem-instructors"')
        self.assertContains(response, 'id="marketing-communications"')
        self.assertContains(response, 'id="apply"')
        self.assertContains(response, 'id="apply-marketing"')

    def test_no_long_dashes_in_page(self):
        response = self.client.get(reverse('careers'))
        content = response.content.decode('utf-8')
        self.assertNotIn('\u2014', content, 'Found em dash in page')
        self.assertNotIn('\u2013', content, 'Found en dash in page')

    def test_commented_wide_img_slot_exists(self):
        response = self.client.get(reverse('careers'))
        self.assertContains(
            response,
            '<!-- <div class="img-slot img-slot--wide"></div> -->',
        )

    def test_footer_contains_careers_link(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, '<a href="/careers/">Careers</a>')

    def test_sitemap_lists_careers_url(self):
        sitemap = StaticViewSitemap()
        self.assertIn('careers', sitemap.items())
        self.assertEqual(sitemap.location('careers'), '/careers/')

    def test_empty_careers_list_shows_only_empty_state(self):
        with mock.patch.object(views, 'CAREERS', []):
            response = self.client.get(reverse('careers'))
            self.assertEqual(response.status_code, 200)
            self.assertContains(
                response,
                'No open roles right now. You are welcome to write to info@mindset-group.org.',
            )
            # Nothing else of the role is shown
            self.assertNotContains(response, 'Associate STEM Instructors')
            self.assertNotContains(response, 'Junior Associate, Marketing & Communications')
            self.assertNotContains(response, 'Who should apply?')
            self.assertNotContains(response, 'What we offer')
            self.assertNotContains(response, 'What you will do')
            self.assertNotContains(response, 'How to apply')
            self.assertNotContains(response, 'Coding and software programming')
            self.assertNotContains(response, 'View details')


class JobApplicationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username='applications-owner',
            email='owner@example.test',
            password='test-password',
        )
        self.owner.groups.add(Group.objects.get(name='Owner'))

    @staticmethod
    def valid_post(**overrides):
        data = {
            'role': views.CAREERS[0]['title'],
            'full_name': 'Test Applicant',
            'email': 'applicant@example.test',
            'phone': '0700123456',
            'cv_link': 'https://example.test/cv',
            'note': 'A short note.',
            'consent': 'on',
            'website': '',
            'form_timestamp': TimestampSigner(
                salt=FORM_TIMESTAMP_SALT
            ).sign(str(time.time() - 4)),
        }
        data.update(overrides)
        return data

    def post_application(self, data):
        with mock.patch(
            'core.views.contact_rate_limit_exceeded',
            return_value=False,
        ):
            return self.client.post(reverse('careers_apply'), data)

    def test_valid_application_is_saved_without_sending_email(self):
        with mock.patch(
            'core.views.contact_rate_limit_exceeded',
            return_value=False,
        ), mock.patch('core.views.send_contact_notification') as notifier:
            response = self.client.post(
                reverse('careers_apply'),
                self.valid_post(),
                follow=True,
            )
            notifier.assert_not_called()
        self.assertEqual(response.status_code, 200)
        application = JobApplication.objects.get()
        self.assertEqual(application.role, views.CAREERS[0]['title'])
        self.assertEqual(application.full_name, 'Test Applicant')
        self.assertEqual(application.email, 'applicant@example.test')
        self.assertEqual(application.phone, '0700123456')
        self.assertEqual(application.cv_link, 'https://example.test/cv')
        self.assertEqual(application.note, 'A short note.')
        self.assertTrue(application.consent)
        self.assertEqual(application.status, 'new')
        self.assertContains(response, 'Your application has been received.')
        self.assertNotContains(response, 'Test Applicant')
        self.assertNotContains(response, 'applicant@example.test')

    def test_valid_application_for_second_role_is_saved(self):
        marketing_role = views.CAREERS[1]['title']
        response = self.client.post(
            reverse('careers_apply'),
            self.valid_post(role=marketing_role),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        application = JobApplication.objects.get(role=marketing_role)
        self.assertEqual(application.role, marketing_role)
        self.assertContains(response, 'Your application has been received.')

    def test_closed_role_disappears_and_direct_apply_is_rejected(self):
        role = views.CAREERS[0]
        CareerRoleState.objects.create(slug=role['slug'], is_open=False)
        careers = self.client.get(reverse('careers'))
        self.assertNotIn(role, careers.context['careers'])
        form = self.client.get(reverse('careers_apply'))
        self.assertNotContains(form, f'<option value="{role["title"]}"')
        direct = self.client.get(reverse('careers_apply'), {'role': role['title']})
        self.assertContains(direct, 'This position is no longer accepting applications')
        self.assertNotContains(direct, f'<option value="{role["title"]}"')
        posted = self.post_application(self.valid_post())
        self.assertContains(posted, 'This position is no longer accepting applications')
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_reopen_role_and_all_roles_closed_empty_state(self):
        CareerRoleState.objects.create(slug=views.CAREERS[0]['slug'], is_open=False)
        self.client.force_login(self.owner)
        response = self.client.post(reverse('team_career_role_toggle', kwargs={'slug': views.CAREERS[0]['slug']}), {'is_open': 'true'})
        self.assertRedirects(response, reverse('team_applications'))
        self.assertTrue(AuditEvent.objects.filter(action='career_role_reopened', object_id=views.CAREERS[0]['slug']).exists())
        self.assertContains(self.client.get(reverse('careers')), views.CAREERS[0]['title'])
        CareerRoleState.objects.update(is_open=False)
        for role in views.CAREERS:
            CareerRoleState.objects.get_or_create(slug=role['slug'], defaults={'is_open': False})
        self.assertContains(self.client.get(reverse('careers')), 'No open roles right now.')

    def test_only_applications_permission_can_toggle_role(self):
        finance = get_user_model().objects.create_user(username='toggle-finance', password='test-password')
        finance.groups.add(Group.objects.get(name='Finance'))
        role = views.CAREERS[0]
        self.client.force_login(finance)
        response = self.client.post(reverse('team_career_role_toggle', kwargs={'slug': role['slug']}), {'is_open': 'false'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(CareerRoleState.objects.filter(slug=role['slug'], is_open=False).exists())

    def test_decline_email_mailto_encodes_address_and_name(self):
        role = views.CAREERS[1]['title']
        app = JobApplication.objects.create(role=role, full_name="O'Neil & Co", email='a&b@example.test', phone='0700123456', cv_link='https://example.test/cv', consent=True, status='declined')
        self.client.force_login(self.owner)
        response = self.client.get(reverse('team_application_detail', kwargs={'pk': app.pk}))
        self.assertContains(response, 'Email applicant')
        link = next(fragment for fragment in html.unescape(response.content.decode()).split('href="') if fragment.startswith('mailto:') and '?subject=' in fragment).split('"', 1)[0]
        parsed = urlparse(link)
        self.assertEqual(unquote(parsed.path), 'a&b@example.test')
        query = parse_qs(parsed.query)
        self.assertIn("O'Neil & Co", query['body'][0])
        self.assertIn(role, query['subject'][0])
        app.status = 'new'
        app.save(update_fields=['status'])
        self.assertNotContains(self.client.get(reverse('team_application_detail', kwargs={'pk': app.pk})), 'Email applicant')

    def test_informed_mark_and_audit_are_private(self):
        app = JobApplication.objects.create(role=views.CAREERS[0]['title'], full_name='Private Person', email='private@example.test', phone='0700123456', cv_link='https://example.test/private', consent=True, status='declined')
        self.client.force_login(self.owner)
        response = self.client.post(reverse('team_application_detail', kwargs={'pk': app.pk}), {'action': 'informed'})
        self.assertRedirects(response, reverse('team_application_detail', kwargs={'pk': app.pk}))
        app.refresh_from_db()
        self.assertIsNotNone(app.informed_at)
        self.assertContains(self.client.get(reverse('team_application_detail', kwargs={'pk': app.pk})), 'Informed')
        event = AuditEvent.objects.get(action='application_informed')
        for private in ('Private Person', 'private@example.test', 'https://example.test/private'):
            self.assertNotIn(private, event.detail)
            self.assertNotIn(private, event.username)

    def test_declined_not_informed_filter(self):
        not_informed = JobApplication.objects.create(role=views.CAREERS[0]['title'], full_name='Waiting Person', email='waiting@example.test', phone='0700123456', cv_link='https://example.test/waiting', consent=True, status='declined')
        JobApplication.objects.create(role=views.CAREERS[0]['title'], full_name='Done Person', email='done@example.test', phone='0700123456', cv_link='https://example.test/done', consent=True, status='declined', informed_at=timezone.now())
        self.client.force_login(self.owner)
        response = self.client.get(reverse('team_applications'), {'informed': 'declined_uninformed'})
        self.assertEqual(response.context['applications'].paginator.count, 1)
        self.assertEqual(response.context['applications'][0], not_informed)

    def test_delete_confirmation_owner_only_post_and_audit(self):
        app = JobApplication.objects.create(role=views.CAREERS[0]['title'], full_name='Delete Person', email='delete@example.test', phone='0700123456', cv_link='https://example.test/delete', consent=True)
        delete_url = reverse('team_application_delete', kwargs={'pk': app.pk})
        finance = get_user_model().objects.create_user(username='delete-finance', password='test-password')
        finance.groups.add(Group.objects.get(name='Finance'))
        self.client.force_login(finance)
        self.assertEqual(self.client.get(delete_url).status_code, 403)
        self.assertEqual(self.client.post(delete_url, {'confirmed': 'true'}).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(delete_url, {}).status_code, 200)
        self.assertTrue(JobApplication.objects.filter(pk=app.pk).exists())
        self.assertEqual(self.client.get(delete_url).status_code, 200)
        self.assertRedirects(self.client.post(delete_url, {'confirmed': 'true'}), reverse('team_applications'))
        self.assertFalse(JobApplication.objects.filter(pk=app.pk).exists())
        event = AuditEvent.objects.get(action='application_deleted')
        for private in ('Delete Person', 'delete@example.test', 'https://example.test/delete'):
            self.assertNotIn(private, event.detail)
            self.assertNotIn(private, event.username)

    def test_get_careers_apply_with_preselected_marketing_role(self):
        marketing_role = views.CAREERS[1]['title']
        response = self.client.get(
            reverse('careers_apply'),
            {'role': marketing_role},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'selected>Junior Associate, Marketing &amp; Communications</option>',
        )

    def test_missing_consent_bad_email_and_bad_url_are_rejected(self):
        invalid_submissions = (
            ('missing consent', {'consent': ''}),
            ('bad email', {'email': 'not-an-email'}),
            ('bad URL', {'cv_link': 'not-a-url'}),
        )
        for label, overrides in invalid_submissions:
            with self.subTest(label=label):
                response = self.post_application(
                    self.valid_post(**overrides)
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'errorlist')
                self.assertEqual(JobApplication.objects.count(), 0)

    def test_cv_link_accepts_only_http_and_https(self):
        for link in ('http://example.test/cv', 'https://example.test/cv'):
            with self.subTest(link=link):
                response = self.post_application(self.valid_post(cv_link=link))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(JobApplication.objects.filter(cv_link=link).exists())

        JobApplication.objects.all().delete()
        invalid_links = (
            'file:///home/applicant/cv.pdf',
            'javascript:alert(1)',
            'data:text/plain,cv',
            'ftp://example.test/cv.pdf',
            'mailto:applicant@example.test',
        )
        for link in invalid_links:
            with self.subTest(link=link):
                response = self.post_application(self.valid_post(cv_link=link))
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    'Enter a valid link using http:// or https://.',
                )
                self.assertEqual(JobApplication.objects.count(), 0)

    def test_cv_link_sharing_hint_is_visible(self):
        response = self.client.get(reverse('careers_apply'))
        self.assertContains(
            response,
            'Use a link that anyone with the link can open, such as a shared Google Drive or Dropbox file.',
        )

    def test_honeypot_is_rejected(self):
        response = self.post_application(
            self.valid_post(website='https://spam.example.test')
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please check your details and send it again.')
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_ip_rate_limit_prevents_saving(self):
        with mock.patch(
            'core.views.contact_rate_limit_exceeded',
            return_value=True,
        ):
            response = self.client.post(
                reverse('careers_apply'),
                self.valid_post(),
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Please wait a while before submitting another application.',
        )
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_save_failure_keeps_input_and_does_not_show_success(self):
        from django.db import OperationalError

        with mock.patch.object(
            JobApplication,
            'save',
            side_effect=OperationalError('database unavailable'),
        ):
            response = self.post_application(self.valid_post())
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Sorry, your application could not be saved. Please try again in a moment.',
        )
        self.assertContains(response, 'Test Applicant')
        self.assertContains(response, 'applicant@example.test')
        self.assertContains(response, '0700123456')
        self.assertContains(response, 'https://example.test/cv')
        self.assertContains(response, 'A short note.')
        self.assertNotContains(response, 'Your application has been received.')
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_validation_database_error_keeps_input_and_returns_friendly_page(self):
        from django.db import OperationalError

        constraint = JobApplication._meta.constraints[0]
        with mock.patch.object(
            constraint,
            'validate',
            side_effect=OperationalError('database unavailable'),
        ):
            response = self.post_application(self.valid_post())
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Sorry, your application could not be saved. Please try again in a moment.',
        )
        self.assertContains(response, 'Test Applicant')
        self.assertContains(response, 'applicant@example.test')
        self.assertContains(response, '0700123456')
        self.assertContains(response, 'https://example.test/cv')
        self.assertContains(response, 'A short note.')
        self.assertNotContains(response, 'Your application has been received.')
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_database_error_during_invalid_timestamp_validation_is_friendly(self):
        from django.db import OperationalError

        constraint = JobApplication._meta.constraints[0]
        with mock.patch.object(
            constraint,
            'validate',
            side_effect=OperationalError('database unavailable'),
        ):
            response = self.post_application(
                self.valid_post(form_timestamp='invalid timestamp')
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Sorry, your application could not be saved. Please try again in a moment.',
        )
        self.assertContains(response, 'Test Applicant')
        self.assertNotContains(response, 'Your application has been received.')
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_apply_page_works_without_role_and_preselects_valid_role(self):
        response = self.client.get(reverse('careers_apply'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['form']['role'].value())

        response = self.client.get(
            reverse('careers_apply'),
            {'role': views.CAREERS[0]['title']},
        )
        self.assertEqual(
            response.context['form']['role'].value(),
            views.CAREERS[0]['title'],
        )
        self.assertContains(
            self.client.get(reverse('careers')),
            'data-umami-event="apply-instructor"',
        )
        self.assertContains(
            self.client.get(reverse('careers')),
            'href="/careers/apply/?role=Associate%20STEM%20Instructors"',
        )

    def test_anonymous_visitor_cannot_see_application_list(self):
        JobApplication.objects.create(
            role=views.CAREERS[0]['title'],
            full_name='Private Applicant',
            email='private@example.test',
            phone='0700123456',
            cv_link='https://example.test/private-cv',
            consent=True,
        )
        response = self.client.get(reverse('team_applications'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(
            'Private Applicant',
            response.content.decode('utf-8'),
        )
        self.assertEqual(
            self.client.get(reverse('team_applications_export')).status_code,
            302,
        )

    def test_public_pages_do_not_show_application_details(self):
        JobApplication.objects.create(
            role=views.CAREERS[0]['title'],
            full_name='Private Applicant',
            email='private@example.test',
            phone='0700123456',
            cv_link='https://example.test/private-cv',
            note='Private application note',
            consent=True,
        )
        for path in (reverse('careers'), reverse('careers_apply')):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            for private_value in (
                'Private Applicant',
                'private@example.test',
                'https://example.test/private-cv',
                'Private application note',
            ):
                with self.subTest(path=path, private_value=private_value):
                    self.assertNotContains(response, private_value)

    def test_team_page_requires_the_people_permission(self):
        finance = get_user_model().objects.create_user(
            username='applications-finance',
            email='finance@example.test',
            password='test-password',
        )
        finance.groups.add(Group.objects.get(name='Finance'))
        self.client.force_login(finance)
        self.assertEqual(
            self.client.get(reverse('team_applications')).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('team_application_detail', kwargs={'pk': 1})).status_code,
            403,
        )

        self.client.force_login(self.owner)
        response = self.client.get(reverse('team_applications'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertIn('no-store', response['Cache-Control'])

    def test_status_change_records_handler_and_activity(self):
        application = JobApplication.objects.create(
            role=views.CAREERS[0]['title'],
            full_name='Status Applicant',
            email='status@example.test',
            phone='0700123456',
            cv_link='https://example.test/status-cv',
            consent=True,
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('team_application_detail', kwargs={'pk': application.pk}),
            {'status': 'shortlisted'},
        )
        self.assertRedirects(
            response,
            reverse('team_application_detail', kwargs={'pk': application.pk}),
        )
        application.refresh_from_db()
        self.assertEqual(application.status, 'shortlisted')
        self.assertEqual(application.handled_by, self.owner)
        event = AuditEvent.objects.get(
            action='job_application_status_changed',
        )
        self.assertEqual(event.object_type, 'JobApplication')
        self.assertEqual(event.object_id, str(application.pk))
        self.assertEqual(event.user, self.owner)
        self.assertNotIn(application.full_name, event.detail)
        audit_page = self.client.get(reverse('team_audit'))
        self.assertContains(audit_page, 'Changed application status')

    def test_csv_export_works_with_role_and_status_filters(self):
        shortlisted = JobApplication.objects.create(
            role=views.CAREERS[0]['title'],
            full_name='CSV Applicant',
            email='csv@example.test',
            phone='0700123456',
            cv_link='https://example.test/csv-cv',
            consent=True,
            status='shortlisted',
        )
        JobApplication.objects.create(
            role=views.CAREERS[0]['title'],
            full_name='Other Applicant',
            email='other@example.test',
            phone='0700123456',
            cv_link='https://example.test/other-cv',
            consent=True,
        )
        self.client.force_login(self.owner)
        listing = self.client.get(reverse('team_applications'), {
            'role': shortlisted.role,
            'status': 'shortlisted',
        })
        self.assertEqual(listing.context['applications'].paginator.count, 1)

        response = self.client.get(reverse('team_applications_export'), {
            'role': shortlisted.role,
            'status': 'shortlisted',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('attachment; filename="applications.csv"', response['Content-Disposition'])
        rows = list(csv.reader(StringIO(response.content.decode('utf-8'))))
        self.assertEqual(rows[0], [
            'Date', 'Name', 'Role', 'Email', 'Phone', 'CV link', 'Note',
            'Consent', 'Status', 'Handled by',
        ])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][1], 'CSV Applicant')
        self.assertEqual(rows[1][8], 'Shortlisted')

    def test_application_detail_shows_private_details_and_cv_link(self):
        application = JobApplication.objects.create(
            role=views.CAREERS[0]['title'],
            full_name='Detail Applicant',
            email='detail@example.test',
            phone='0700123456',
            cv_link='https://example.test/detail-cv',
            note='Application note',
            consent=True,
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('team_application_detail', kwargs={'pk': application.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Applicant')
        self.assertContains(response, 'detail@example.test')
        self.assertContains(response, 'href="https://example.test/detail-cv"')
        self.assertContains(response, 'Application note')

    def test_team_detail_links_only_http_and_https_cv_urls(self):
        self.client.force_login(self.owner)
        links = (
            ('http://example.test/http-cv', True),
            ('https://example.test/https-cv', True),
            ('file:///private/cv.pdf', False),
            ('javascript:alert(1)', False),
            ('data:text/plain,cv', False),
            ('ftp://example.test/cv.pdf', False),
        )
        for link, clickable in links:
            with self.subTest(link=link):
                application = JobApplication.objects.create(
                    role=views.CAREERS[0]['title'],
                    full_name='CV Applicant',
                    email='cv@example.test',
                    phone='0700123456',
                    cv_link=link,
                    consent=True,
                )
                response = self.client.get(
                    reverse('team_application_detail', kwargs={'pk': application.pk})
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, link)
                if clickable:
                    self.assertContains(
                        response,
                        f'href="{link}" target="_blank" rel="noopener noreferrer"',
                    )
                else:
                    self.assertNotContains(response, f'href="{link}"')
