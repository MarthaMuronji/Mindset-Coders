import csv
import time
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.signing import TimestampSigner
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import views
from .models import AuditEvent, JobApplication
from .spam import FORM_TIMESTAMP_SALT
from .sitemaps import StaticViewSitemap


class CareersPageTests(SimpleTestCase):
    def test_careers_page_renders_without_a_database_and_returns_200(self):
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
            '<title>Careers | Associate STEM Instructor | Mindset Coders Uganda</title>',
        )
        self.assertContains(
            response,
            '<meta name="description" content="Mindset Coders is expanding its team of instructors passionate about technology, education and inspiring the next generation of innovators.">',
        )
        self.assertContains(
            response,
            '<meta property="og:title" content="Careers | Associate STEM Instructor | Mindset Coders Uganda">',
        )
        self.assertContains(
            response,
            '<meta property="og:description" content="Mindset Coders is expanding its team of instructors passionate about technology, education and inspiring the next generation of innovators.">',
        )
        self.assertContains(
            response,
            '<link rel="canonical" href="http://testserver/careers/">',
        )

    def test_careers_page_shows_headings_and_exact_role_copy(self):
        response = self.client.get(reverse('careers'))

        # Badge and headings
        self.assertContains(response, '<span class="badge">Careers</span>')
        self.assertContains(response, '<h1>We are hiring!</h1>')
        self.assertContains(response, 'Associate STEM Instructors')

        # Chips
        self.assertContains(response, 'Part-Time')
        self.assertContains(response, 'Entry-Level')
        self.assertContains(response, 'Kampala')

        # Intro and lead in
        self.assertContains(
            response,
            'Mindset Coders is expanding its team of instructors passionate about technology, education and inspiring the next generation of innovators.',
        )
        self.assertContains(
            response,
            'We are looking for enthusiastic, reliable and curious individuals interested in teaching children and young people in the following areas:',
        )

        # 4 Area cards
        for card_title in (
            'Coding and software programming',
            'Robotics and electronics',
            'Foundational STEM education',
            'Design thinking and innovation',
        ):
            self.assertContains(response, card_title)

        # Who should apply section and every list item
        self.assertContains(response, '<h2>Who should apply?</h2>')
        for item in (
            'Recent graduates and early-career professionals in STEM, computer science, engineering, IT, education or related fields.',
            'Individuals with practical technical skills and a willingness to learn.',
            'Individuals who enjoy working with children and young people.',
            'Reliable, punctual and proactive individuals with strong communication skills.',
            'Individuals available for scheduled weekday and/or weekend teaching assignments.',
        ):
            self.assertContains(response, item)

        # Note
        self.assertContains(
            response,
            'Previous teaching experience is an advantage but is not mandatory.',
        )

        # What we offer section and every list item
        self.assertContains(response, '<h2>What we offer</h2>')
        for item in (
            'Instructor training and professional development.',
            'Access to structured curricula and teaching resources.',
            'Practical experience delivering STEM education programmes.',
            'Paid teaching assignments.',
            'Opportunities for professional growth within Mindset Coders.',
        ):
            self.assertContains(response, item)

        # Paragraph and Location
        self.assertContains(
            response,
            'This is a part-time, assignment-based opportunity for individuals who are committed to learning, delivering quality work and growing with an ambitious education technology company.',
        )
        self.assertContains(response, 'Kampala, Uganda')

        # How to apply section
        self.assertContains(response, '<h2>How to apply</h2>')
        self.assertContains(
            response,
            'Send your CV and a brief introduction highlighting your technical skills, interests and availability to info@mindset-group.org.',
        )
        self.assertContains(response, 'info@mindset-group.org')
        self.assertContains(
            response,
            'Subject: Associate STEM Instructor Application',
        )
        self.assertContains(
            response,
            'Mindset Coders | BIG IDEAS START HERE',
        )

    def test_apply_button_link_and_umami_tracking(self):
        response = self.client.get(reverse('careers'))
        self.assertContains(
            response,
            'href="/careers/apply/?role=Associate%20STEM%20Instructors"',
        )
        self.assertContains(response, 'data-umami-event="apply-instructor"')
        self.assertContains(response, 'data-umami-event-from="careers"')
        self.assertContains(response, 'Apply')

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
            self.assertNotContains(response, 'Who should apply?')
            self.assertNotContains(response, 'What we offer')
            self.assertNotContains(response, 'How to apply')
            self.assertNotContains(response, 'Coding and software programming')
            self.assertNotContains(response, 'Apply by email')
            self.assertNotContains(response, 'BIG IDEAS START HERE')


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
