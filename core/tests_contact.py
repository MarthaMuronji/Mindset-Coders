"""The Contact page: the phone number on the form, and the shared links.

The project has no database in its test setup, so every test uses
SimpleTestCase. The tests that save patch ContactMessage.objects.create,
which is the only thing that would otherwise reach a database.
"""
import html
import json
import os
from unittest import mock

from django.test import SimpleTestCase, override_settings

from .forms import ContactForm
from .models import ContactMessage, Registration, Story
from .notifications import send_contact_notification
from .registration import RegistrationForm, send_registration_notification
from .views import STEAM_EXPERIENCE


WHATSAPP_LINK = (
    'href="https://wa.me/256752064343" target="_blank" '
    'rel="noopener noreferrer"'
)
PHONE_LINK = 'href="tel:+256752064343"'

# A complete, valid submission. Nothing here describes a real person.
VALID_POST = {
    'name': 'Test Person',
    'email': 'person@example.com',
    'phone': '+256 700 000000',
    'role': 'parent',
    'message': 'Hello there, I have a question.',
}

# The one sentence every phone problem shows
FRIENDLY_ERROR = 'Please enter a phone number we can call, for example +256 7XX XXX XXX.'

# The three environment variables that switch the notification email on
BREVO_ENVIRONMENT = {
    'BREVO_API_KEY': 'test-key',
    'CONTACT_NOTIFY_EMAIL': 'team@example.com',
    'CONTACT_FROM_EMAIL': 'website@example.com',
}


class ContactLinksTests(SimpleTestCase):
    def test_whatsapp_and_phone_links_render_on_each_page(self):
        with override_settings(STEAM_PAYMENTS_ENABLED=True):
            confirmation = self.client.get(
                '/join/thanks/?programme=holiday&stage=build'
            )
        responses = {
            'confirmation': confirmation,
            'STEAM Experience': self.client.get('/steam-experience/'),
            'Contact': self.client.get('/contact/'),
        }

        for name, response in responses.items():
            with self.subTest(page=name):
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, WHATSAPP_LINK)
                self.assertContains(response, PHONE_LINK)

    def test_cash_copy_only_appears_with_confirmation_payment(self):
        with override_settings(STEAM_PAYMENTS_ENABLED=True):
            paid = self.client.get(
                '/join/thanks/?programme=holiday&stage=build'
            )
        with override_settings(STEAM_PAYMENTS_ENABLED=False):
            plain = self.client.get(
                '/join/thanks/?programme=holiday&stage=build'
            )

        self.assertContains(
            paid, 'You can also pay in cash. Contact our team to arrange it.'
        )
        self.assertNotContains(
            plain, 'You can also pay in cash. Contact our team to arrange it.'
        )

    def test_payment_options_include_mobile_money_and_cash(self):
        self.assertEqual(
            STEAM_EXPERIENCE['payment_options'],
            'Pay online by Mobile Money. You can also pay in cash.',
        )


class ContactPhonePageTests(SimpleTestCase):
    """The phone field on the contact page itself."""

    def test_the_page_renders_the_field_between_email_and_the_role(self):
        response = self.client.get('/contact/')
        self.assertEqual(response.status_code, 200)
        # The label, the box and the hint under it are all on the page
        self.assertContains(response, 'id="id_phone"')
        self.assertContains(response, 'Phone number')
        self.assertContains(response, 'So our team can call you back.')
        # Exactly where it was asked for: after Email, before the next field
        page = response.content.decode('utf-8')
        self.assertLess(
            page.index('id="id_email"'), page.index('id="id_phone"')
        )
        self.assertLess(
            page.index('id="id_phone"'), page.index('id="id_role"')
        )

    def test_the_form_asks_for_a_required_phone_number(self):
        phone = ContactForm.base_fields['phone']
        self.assertTrue(phone.required)
        self.assertEqual(phone.label, 'Phone number')
        self.assertEqual(phone.help_text, 'So our team can call you back.')

    def test_the_topic_still_prefills_the_message_box(self):
        response = self.client.get('/contact/?topic=school')
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'I would like to bring STEAM to our school.'
        )

    def test_an_unknown_topic_prefills_nothing(self):
        response = self.client.get('/contact/?topic=party')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response, 'I would like to bring STEAM to our school.'
        )


class ContactPhoneFormTests(SimpleTestCase):
    """Validating, saving and emailing one message with a phone number."""

    def post_form(self, data, follow=False):
        """POST with saving and emailing fully worked out.

        ContactMessage.objects.create is patched, so the view still
        builds and saves a message but nothing reaches a database, and
        urlopen is patched, so nothing leaves the machine either.
        """
        saved = []

        def fake_create(**kwargs):
            # Built in memory with a made up key, so the view can carry
            # on exactly as it would with a real row
            contact_message = ContactMessage(pk=1, **kwargs)
            saved.append(contact_message)
            return contact_message

        with mock.patch.object(
            ContactMessage.objects, 'create', side_effect=fake_create
        ) as create_mock:
            with mock.patch.dict(os.environ, BREVO_ENVIRONMENT):
                with mock.patch(
                    'core.notifications.urllib.request.urlopen'
                ) as send:
                    response = self.client.post('/contact/', data, follow=follow)
        payload = None
        if send.call_count:
            request = send.call_args.args[0]
            payload = json.loads(request.data.decode('utf-8'))
        return response, saved, payload, create_mock

    def test_a_valid_message_with_a_phone_saves(self):
        response, saved, payload, _create = self.post_form(VALID_POST)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/contact/')
        self.assertEqual(len(saved), 1)
        message = saved[0]
        self.assertEqual(message.name, 'Test Person')
        self.assertEqual(message.email, 'person@example.com')
        self.assertEqual(message.phone, '+256 700 000000')
        self.assertEqual(message.role, 'parent')
        self.assertEqual(message.message, 'Hello there, I have a question.')

    def test_the_saved_message_shows_the_same_success_message(self):
        response, _saved, _payload, _create = self.post_form(
            VALID_POST, follow=True
        )
        # The apostrophe reaches the page HTML-escaped, as it always has
        page = html.unescape(response.content.decode('utf-8'))
        self.assertIn("Thanks for reaching out! We'll be in touch soon.", page)

    def test_the_notification_email_carries_the_phone_line(self):
        _response, _saved, payload, _create = self.post_form(VALID_POST)
        self.assertIsNotNone(payload)
        lines = payload['textContent'].split('\n')
        # Directly after the email line, and nothing else moved
        self.assertIn('Email: person@example.com', lines)
        email_at = lines.index('Email: person@example.com')
        self.assertEqual(lines[email_at + 1], 'Phone: +256 700 000000')
        self.assertEqual(lines[email_at - 1], 'Name: Test Person')
        self.assertEqual(
            payload['replyTo']['email'], 'person@example.com'
        )

    def test_a_missing_phone_fails_with_the_friendly_error(self):
        data = dict(VALID_POST)
        data.pop('phone')
        response, saved, _payload, create_mock = self.post_form(data)
        create_mock.assert_not_called()
        self.assertEqual(saved, [])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errorlist')
        self.assertContains(response, FRIENDLY_ERROR)

    def test_a_blank_phone_fails_too(self):
        response, _saved, _payload, create_mock = self.post_form(
            dict(VALID_POST, phone='   ')
        )
        create_mock.assert_not_called()
        self.assertContains(response, FRIENDLY_ERROR)

    def test_a_short_number_fails(self):
        # Too short, far too long, and letters instead of digits
        for phone in ('12345', '1234567890123456', 'call me maybe'):
            with self.subTest(phone=phone):
                response, _saved, _payload, create_mock = self.post_form(
                    dict(VALID_POST, phone=phone)
                )
                create_mock.assert_not_called()
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'errorlist')
                self.assertContains(response, FRIENDLY_ERROR)

    def test_spaces_and_a_leading_plus_are_accepted(self):
        # A leading plus, spaces, brackets and hyphens are all welcome
        for phone in ('+256 700 123456', '256 700 123 456', '(020) 741-000-222', '0771234567'):
            with self.subTest(phone=phone):
                response, saved, _payload, _create = self.post_form(
                    dict(VALID_POST, phone=phone)
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(len(saved), 1)
                self.assertEqual(saved[0].phone, phone)

    def test_a_save_failure_keeps_the_typed_input_and_shows_the_error(self):
        with mock.patch.object(
            ContactMessage.objects, 'create', side_effect=RuntimeError('down')
        ):
            with mock.patch(
                'core.views.send_contact_notification'
            ) as notify:
                response = self.client.post('/contact/', VALID_POST)
        notify.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'Sorry, we could not send your message. Please try again in a moment.'
        )
        # Everything the visitor typed is still in the form
        self.assertContains(response, 'Test Person')
        self.assertContains(response, 'person@example.com')
        self.assertContains(response, '+256 700 000000')

    def test_a_failing_email_never_reaches_the_visitor(self):
        def boom(contact_message, admin_url):
            raise RuntimeError('smtp is down')

        with mock.patch('core.views.send_contact_notification', boom):
            with mock.patch.object(
                ContactMessage.objects,
                'create',
                side_effect=lambda **kwargs: ContactMessage(pk=1, **kwargs),
            ):
                response = self.client.post(
                    '/contact/', VALID_POST, follow=True
                )
        # The message was saved and the visitor is simply sent on
        page = html.unescape(response.content.decode('utf-8'))
        self.assertIn("Thanks for reaching out! We'll be in touch soon.", page)


class ContactNotificationTests(SimpleTestCase):
    """The shared Brevo helper, as the contact form uses it."""

    def send(self, contact_message, review_url=None):
        """Send with the environment switched on and the API stubbed."""
        with mock.patch.dict(os.environ, BREVO_ENVIRONMENT):
            with mock.patch('core.notifications.urllib.request.urlopen') as send:
                send_contact_notification(
                    contact_message,
                    'http://testserver/admin/core/contactmessage/1/change/',
                    review_url,
                )
        self.assertEqual(send.call_count, 1)
        request = send.call_args.args[0]
        return json.loads(request.data.decode('utf-8'))

    def test_the_phone_line_sits_between_the_email_and_the_role(self):
        contact_message = ContactMessage(
            name='Test Person',
            email='person@example.com',
            phone='+256 700 000000',
            role='parent',
            message='Hello there.',
        )
        lines = self.send(contact_message)['textContent'].split('\n')
        self.assertEqual(lines[2], 'Name: Test Person')
        self.assertEqual(lines[3], 'Email: person@example.com')
        self.assertEqual(lines[4], 'Phone: +256 700 000000')
        self.assertEqual(lines[5], 'Role: parent')

    def test_an_older_message_with_no_phone_keeps_the_old_lines(self):
        # Rows saved before the phone field existed carry no phone, so
        # their email keeps exactly the lines it had before
        contact_message = ContactMessage(
            name='Test Person',
            email='person@example.com',
            role='parent',
            message='Hello there.',
        )
        lines = self.send(contact_message)['textContent'].split('\n')
        self.assertEqual(lines[2], 'Name: Test Person')
        self.assertEqual(lines[3], 'Email: person@example.com')
        self.assertEqual(lines[4], 'Role: parent')
        self.assertFalse(any(line.startswith('Phone:') for line in lines))

    def test_the_story_email_never_carries_a_phone_line(self):
        # The same helper sends story emails, and a story has no phone
        story = Story(
            name='Test Person',
            email='person@example.com',
            role='learner',
            category='learner',
            story='Once upon a time.',
            display_as='anonymous',
            consent=True,
        )
        payload = self.send(story, 'http://testserver/review/')
        lines = payload['textContent'].split('\n')
        self.assertIn('Email: person@example.com', lines)
        self.assertFalse(any(line.startswith('Phone:') for line in lines))
        # The review link still travels with a story
        self.assertIn('Review this story: http://testserver/review/', lines)


class ContactPhoneLeavesJoinTests(SimpleTestCase):
    """The phone field on the contact form belongs to that form only."""

    def test_the_registration_form_is_unchanged(self):
        # The Join form still asks for exactly what it asked for before,
        # in the same order, with the same phone label of its own
        self.assertEqual(
            list(RegistrationForm._meta.fields),
            [
                'parent_name', 'parent_email', 'parent_phone', 'learner_name',
                'learner_age', 'school_name', 'programme', 'stage', 'consent',
            ],
        )
        phone = RegistrationForm.base_fields['parent_phone']
        self.assertEqual(phone.label, 'Your phone number')
        # The new phone field belongs to the contact form only, and the
        # contact form kept every field it had
        self.assertEqual(
            list(ContactForm.base_fields),
            ['name', 'email', 'phone', 'role', 'message'],
        )

    def test_the_join_page_never_asks_for_the_new_field(self):
        response = self.client.get('/join/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_parent_phone"')
        self.assertNotContains(response, 'id="id_phone"')

    def test_the_registration_email_carries_no_phone_line(self):
        registration = Registration(
            parent_name='Test Parent',
            parent_email='parent@example.com',
            parent_phone='+256 700 000000',
            learner_name='Test Learner',
            learner_age=10,
            school_name='',
            programme='holiday',
            consent=True,
        )
        with mock.patch.dict(os.environ, BREVO_ENVIRONMENT):
            with mock.patch(
                'core.registration.urllib.request.urlopen'
            ) as send:
                send_registration_notification(
                    registration,
                    'http://testserver/admin/core/registration/1/change/',
                )
        request = send.call_args.args[0]
        body = json.loads(request.data.decode('utf-8'))['textContent']
        self.assertNotIn('Phone', body)
        # The registration email never carried any personal detail
        for value in ('Test Parent', 'parent@example.com', '+256 700 000000'):
            with self.subTest(value=value):
                self.assertNotIn(value, body)

    def test_the_intro_copy_is_unchanged(self):
        # The line above the form is the one the page has always shown,
        # so nothing else on the form moved
        response = self.client.get('/contact/')
        self.assertContains(
            response, 'Tell us a little about what you need and we will read your message.'
        )

