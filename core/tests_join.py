"""The Join page, the parent registration form and the old Mindset Learn address.

The project has no database in its test setup, so every test uses
SimpleTestCase. The tests that save patch Registration.save, which is the
only thing that would otherwise reach a database.
"""
import json
import os
import re
from unittest import mock

from django.contrib.messages import get_messages
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from .models import Registration
from .registration import send_registration_notification

# A complete, valid submission. Nothing here describes a real person.
VALID_POST = {
    'parent_name': 'Test Parent',
    'parent_email': 'parent@example.com',
    'parent_phone': '+256 700 000000',
    'learner_name': 'Test Learner',
    'learner_age': '10',
    'school_name': '',
    'programme': 'holiday',
    'stage': 'discover',
    'consent': 'on',
    'website': '',
}

# The four programme values the select offers
PROGRAMMES = ('holiday', 'weekend', 'school', 'unsure')

# The four stage values the select offers
STAGES = ('discover', 'build', 'innovate', 'full')


class JoinPageTests(SimpleTestCase):
    """The Join form: rendering, saving, validation and the spam trap."""

    def post_form(self, data):
        """POST with saving and emailing replaced by recorders.

        The model's save is patched, so the view still builds and saves a
        Registration but nothing reaches a database.
        """
        saved = []
        notified = []

        def fake_save(instance, *args, **kwargs):
            # A made up key, so the view can build the admin link
            instance.pk = 42
            saved.append(instance)

        def fake_notify(registration, admin_url):
            notified.append((registration, admin_url))

        with mock.patch.object(Registration, 'save', fake_save):
            with mock.patch(
                'core.registration.send_registration_notification', fake_notify
            ):
                response = self.client.post('/join/', data)
        return response, saved, notified

    @staticmethod
    def option_tag(response, value):
        """The <option> element for one programme value, or an empty string."""
        match = re.search(
            r'<option value="%s"[^>]*>' % re.escape(value),
            response.content.decode(),
        )
        return match.group() if match else ''

    def test_page_renders_without_a_database(self):
        # SimpleTestCase fails any test that touches the database, so a
        # successful 200 here proves the page renders without one.
        response = self.client.get('/join/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Join Mindset Coders')
        self.assertIn('form', response.context)

    def test_url_names(self):
        # The sitemap and every link reverse these two names
        self.assertEqual(reverse('join'), '/join/')
        self.assertEqual(reverse('join_thanks'), '/join/thanks/')

    def test_page_carries_the_copy(self):
        response = self.client.get('/join/')
        for text in (
            'Join Mindset Coders',
            'Tell us about your child and the programme you are interested in. '
            'Our team will get in touch with the next steps.',
            'Read how we handle your information on our',
            'Send my registration',
        ):
            with self.subTest(text=text):
                self.assertContains(response, text)
        # The privacy line points at the privacy page
        self.assertContains(response, 'href="/privacy/"')

    def test_labels_are_the_ones_asked_for(self):
        response = self.client.get('/join/')
        labels = response.context['form'].fields
        expected = {
            'parent_name': 'Your name',
            'parent_email': 'Your email',
            'parent_phone': 'Your phone number',
            'learner_name': "Learner's name",
            'learner_age': "Learner's age",
            'school_name': 'School (optional)',
            'programme': 'Programme',
            'stage': 'Stage',
            'consent': 'I am the parent or guardian of this learner, and I agree '
                       'to Mindset Coders contacting me about this registration.',
        }
        for field, label in expected.items():
            with self.subTest(field=field):
                self.assertEqual(labels[field].label, label)

    def test_valid_post_saves_and_redirects(self):
        response, saved, notified = self.post_form(VALID_POST)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'], '/join/thanks/?programme=holiday&stage=discover'
        )

        self.assertEqual(len(saved), 1)
        registration = saved[0]
        self.assertEqual(registration.parent_name, 'Test Parent')
        self.assertEqual(registration.parent_email, 'parent@example.com')
        self.assertEqual(registration.parent_phone, '+256 700 000000')
        self.assertEqual(registration.learner_name, 'Test Learner')
        self.assertEqual(registration.learner_age, 10)
        self.assertEqual(registration.school_name, '')
        self.assertEqual(registration.programme, 'holiday')
        self.assertEqual(registration.stage, 'discover')
        self.assertTrue(registration.consent)
        self.assertFalse(registration.handled)

        # The team is emailed about it, with a link to this record in the
        # admin, and never with any personal details
        self.assertEqual(len(notified), 1)
        self.assertIs(notified[0][0], registration)
        self.assertEqual(
            notified[0][1],
            'http://testserver/admin/core/registration/42/change/',
        )

    def test_missing_consent_fails(self):
        data = dict(VALID_POST)
        data.pop('consent')
        with mock.patch.object(Registration, 'save') as save_mock:
            response = self.client.post('/join/', data)
        save_mock.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errorlist')
        self.assertContains(
            response,
            'Please tick this box so we can contact you about this registration.',
        )

    def test_bad_age_fails(self):
        # Too old, too young and not a number at all
        for age in ('99', '2', 'abc'):
            with self.subTest(age=age):
                data = dict(VALID_POST, learner_age=age)
                with mock.patch.object(Registration, 'save') as save_mock:
                    response = self.client.post('/join/', data)
                save_mock.assert_not_called()
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'errorlist')
                self.assertContains(response, 'between 3 and 25.')

    def test_honeypot_saves_nothing(self):
        data = dict(VALID_POST, website='https://spam.example.com')
        response, saved, notified = self.post_form(data)
        self.assertEqual(saved, [])
        self.assertEqual(notified, [])
        # The visitor sees the same thank you page as anyone else
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/join/thanks/')

    def test_save_failure_shows_an_error_and_keeps_the_text(self):
        def broken_save(instance, *args, **kwargs):
            raise RuntimeError('database is down')

        with mock.patch.object(Registration, 'save', broken_save):
            with mock.patch(
                'core.registration.send_registration_notification'
            ) as notify:
                response = self.client.post('/join/', VALID_POST)
        notify.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Sorry, we could not send your registration. Please try again in a moment.',
        )
        # Everything the visitor typed is still in the form
        self.assertContains(response, 'Test Learner')
        self.assertContains(response, 'parent@example.com')

    def test_a_failing_email_never_reaches_the_visitor(self):
        def boom(registration, admin_url):
            raise RuntimeError('smtp is down')

        with mock.patch.object(Registration, 'save') as save_mock:
            with mock.patch(
                'core.registration.send_registration_notification', boom
            ):
                response = self.client.post('/join/', VALID_POST)
        # The registration was saved and the visitor is simply sent on
        save_mock.assert_called()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'], '/join/thanks/?programme=holiday&stage=discover'
        )
        # No message is waiting for them, so nothing can be shown as an error
        self.assertEqual(list(get_messages(response.wsgi_request)), [])

    def test_mindset_learn_redirects_to_join(self):
        response = self.client.get('/mindset-learn/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/join/')

    def test_programme_query_param_preselects(self):
        response = self.client.get('/join/?programme=holiday')
        self.assertEqual(response.status_code, 200)
        self.assertIn('selected', self.option_tag(response, 'holiday'))
        for value in PROGRAMMES:
            if value != 'holiday':
                with self.subTest(value=value):
                    self.assertNotIn('selected', self.option_tag(response, value))

    def test_an_unknown_programme_is_not_preselected(self):
        response = self.client.get('/join/?programme=party')
        for value in PROGRAMMES:
            with self.subTest(value=value):
                self.assertNotIn('selected', self.option_tag(response, value))

    def test_stage_is_required_for_the_holiday_programme_only(self):
        data = dict(VALID_POST)
        data.pop('stage')
        with mock.patch.object(Registration, 'save') as save_mock:
            response = self.client.post('/join/', data)
        save_mock.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errorlist')
        self.assertContains(
            response, 'Please choose a stage for the Holiday STEAM Experience.'
        )

        # Every other programme saves with no stage at all
        for programme in ('weekend', 'school', 'unsure'):
            with self.subTest(programme=programme):
                data = dict(VALID_POST, programme=programme)
                data.pop('stage')
                response, saved, notified = self.post_form(data)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(len(saved), 1)

    def test_a_stage_on_another_programme_is_cleared(self):
        data = dict(VALID_POST, programme='weekend', stage='discover')
        response, saved, notified = self.post_form(data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(saved[0].programme, 'weekend')
        self.assertEqual(saved[0].stage, '')

    def test_the_redirect_carries_only_the_programme_and_the_stage(self):
        data = dict(VALID_POST, learner_name='A Name That Must Not Travel')
        response, saved, notified = self.post_form(data)
        location = response['Location']
        self.assertEqual(
            location, '/join/thanks/?programme=holiday&stage=discover'
        )
        # No name, age or contact detail ever lands in the address
        for value in (
            'A Name That Must Not Travel',
            'Test Parent',
            'parent@example.com',
            '+256 700 000000',
            '10',
        ):
            with self.subTest(value=value):
                self.assertNotIn(value, location)

    def test_stage_query_param_preselects(self):
        response = self.client.get('/join/?stage=innovate')
        self.assertEqual(response.status_code, 200)
        self.assertIn('selected', self.option_tag(response, 'innovate'))
        for value in STAGES:
            if value != 'innovate':
                with self.subTest(value=value):
                    self.assertNotIn('selected', self.option_tag(response, value))

    def test_an_unknown_stage_is_not_preselected(self):
        response = self.client.get('/join/?stage=party')
        for value in STAGES:
            with self.subTest(value=value):
                self.assertNotIn('selected', self.option_tag(response, value))

    def test_the_stage_field_shows_its_hint(self):
        response = self.client.get('/join/')
        self.assertContains(
            response,
            'Choose a stage if you picked the Holiday STEAM Experience.',
        )

    @override_settings(STEAM_EXPERIENCE_PUBLIC=False)
    def test_no_steam_link_while_the_page_is_not_public(self):
        for url in ('/join/', '/join/thanks/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, '/steam-experience/')

    @override_settings(STEAM_EXPERIENCE_PUBLIC=True)
    def test_steam_button_once_the_page_is_public(self):
        response = self.client.get('/join/thanks/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'See the STEAM Experience')
        self.assertContains(response, 'href="/steam-experience/"')


class JoinThanksPageTests(SimpleTestCase):
    """The page shown after a registration has been stored."""

    def test_page_carries_the_copy(self):
        response = self.client.get('/join/thanks/')
        self.assertEqual(response.status_code, 200)
        for text in (
            'Thank you',
            'We have received your registration. Our team will get in touch '
            'with you about the next steps.',
            'Questions? Call',
            '+256 752 064343',
            'Monday to Saturday, 8:00 am to 6:00 pm.',
        ):
            with self.subTest(text=text):
                self.assertContains(response, text)
        # The number is dialled exactly the way the Contact page dials it
        self.assertContains(response, 'href="tel:+256752064343"')

    @override_settings(STEAM_EXPERIENCE_PUBLIC=False)
    def test_sent_event_fires_like_the_contact_page(self):
        response = self.client.get('/join/thanks/')
        self.assertContains(response, "window.umami.track('join-form-sent')")

    def test_register_another_child_always_offered(self):
        # On the plain page and on any programme, there is always a way
        # back to the form for the next child
        for url in (
            '/join/thanks/',
            '/join/thanks/?programme=weekend&stage=',
            '/join/thanks/?programme=holiday&stage=discover',
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Register another child')
                self.assertContains(response, 'href="/join/?programme=holiday"')


class RegistrationNotificationTests(SimpleTestCase):
    """The Brevo email the team receives about a new registration."""

    def build_registration(self):
        # Built in memory only: nothing here is saved anywhere
        return Registration(
            parent_name='Test Parent',
            parent_email='parent@example.com',
            parent_phone='+256 700 000000',
            learner_name='Test Learner',
            learner_age=10,
            school_name='',
            programme='holiday',
            consent=True,
        )

    def send(self, registration, admin_url='http://testserver/admin/core/registration/1/change/'):
        """Send with the three environment variables set and the API stubbed."""
        environment = {
            'BREVO_API_KEY': 'test-key',
            'CONTACT_NOTIFY_EMAIL': 'team@example.com',
            'CONTACT_FROM_EMAIL': 'website@example.com',
        }
        with mock.patch.dict(os.environ, environment):
            with mock.patch('core.registration.urllib.request.urlopen') as send:
                send_registration_notification(registration, admin_url)
        self.assertEqual(send.call_count, 1)
        request = send.call_args.args[0]
        return json.loads(request.data.decode('utf-8'))

    def test_subject_and_no_reply_to(self):
        payload = self.send(self.build_registration())
        self.assertEqual(payload['subject'], 'New registration received')
        # The email carries no personal details, so a reply could never
        # reach the parent
        self.assertNotIn('replyTo', payload)

    def test_body_is_one_line_with_the_programme_and_the_admin_link(self):
        payload = self.send(self.build_registration())
        body = payload['textContent']
        self.assertNotIn('\n', body)
        self.assertIn('A new registration was received', body)
        self.assertIn('Holiday STEAM Experience', body)
        self.assertIn('http://testserver/admin/core/registration/1/change/', body)

    def test_body_carries_no_personal_details(self):
        payload = self.send(self.build_registration())
        body = payload['textContent']
        for value in (
            'Test Parent',
            'parent@example.com',
            '+256 700 000000',
            'Test Learner',
            '10',
        ):
            with self.subTest(value=value):
                self.assertNotIn(value, body)

    def test_nothing_is_sent_without_the_environment(self):
        # Without the three variables the feature is off and the function
        # returns quietly, so local development needs no setup
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch('core.registration.urllib.request.urlopen') as send:
                send_registration_notification(
                    self.build_registration(), 'http://testserver/admin/'
                )
        send.assert_not_called()
