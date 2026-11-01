from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from .models import ContactMessage, Registration


class TeamPagesTests(TestCase):
    password = 'team-test-password'

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='team-member',
            password=self.password,
        )
        self.registration = self.make_registration()
        self.contact_message = ContactMessage.objects.create(
            name='Parent Example',
            email='parent@example.com',
            phone='0700123456',
            role='parent',
            message='Please call me about the programme.',
        )

    def make_registration(self, **overrides):
        values = {
            'parent_name': 'Parent Example',
            'parent_email': 'parent@example.com',
            'parent_phone': '+256 700 123456',
            'learner_name': 'Learner Example',
            'learner_age': 11,
            'school_name': 'Example School',
            'programme': 'holiday',
            'stage': 'build',
            'payment_method': 'cash',
            'payment_status': 'pending',
            'amount_due': 400000,
            'amount_paid': 0,
            'consent': True,
        }
        values.update(overrides)
        return Registration.objects.create(**values)

    def grant(self, model, *codenames):
        content_type = ContentType.objects.get_for_model(model)
        permissions = Permission.objects.filter(
            content_type=content_type,
            codename__in=codenames,
        )
        self.user.user_permissions.add(*permissions)

    def login_with(self, *permissions):
        self.grant(Registration, *permissions)
        self.client.force_login(self.user)

    def test_signed_out_visitors_return_to_the_requested_registration(self):
        url = reverse(
            'team_registration_detail',
            kwargs={'pk': self.registration.pk},
        )
        response = self.client.get(url)
        self.assertRedirects(
            response,
            '{}?next={}'.format(reverse('team_login'), url),
        )
        self.grant(Registration, 'view_registration')
        response = self.client.post(reverse('team_login'), {
            'username': self.user.username,
            'password': self.password,
            'next': url,
        })
        self.assertRedirects(response, url)

    def test_user_without_permission_gets_a_friendly_403(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('team_registrations'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'You do not have access', status_code=403)

    def test_view_permission_allows_registration_list_and_detail(self):
        self.login_with('view_registration')
        list_response = self.client.get(reverse('team_registrations'))
        detail_response = self.client.get(reverse(
            'team_registration_detail',
            kwargs={'pk': self.registration.pk},
        ))
        self.assertContains(list_response, 'Learner Example')
        self.assertContains(detail_response, 'Parent Example')
        self.assertContains(detail_response, '+256 700 123456')
        self.assertContains(detail_response, 'wa.me/256700123456')
        self.assertContains(detail_response, 'Example School')
        self.assertContains(detail_response, 'UGX 400000')

    def test_change_actions_are_denied_without_change_permission(self):
        self.login_with('view_registration')
        action_url = reverse(
            'team_registration_action',
            kwargs={'pk': self.registration.pk, 'action': 'paid'},
        )
        response = self.client.post(action_url)
        self.assertEqual(response.status_code, 403)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.payment_status, 'pending')
        detail_url = reverse(
            'team_registration_detail',
            kwargs={'pk': self.registration.pk},
        )
        response = self.client.post(detail_url, {'payment_note': 'Private note'})
        self.assertEqual(response.status_code, 403)

    def test_payment_actions_refuse_get_and_require_confirmation(self):
        self.login_with('view_registration', 'change_registration')
        action_url = reverse(
            'team_registration_action',
            kwargs={'pk': self.registration.pk, 'action': 'paid'},
        )
        response = self.client.get(action_url)
        self.assertEqual(response.status_code, 405)
        response = self.client.post(action_url)
        self.assertEqual(response.status_code, 200)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.payment_status, 'pending')
        self.assertContains(response, 'name="confirmed" value="true"')

    def test_mark_paid_sets_amount_timestamp_receipt_and_username(self):
        self.login_with('view_registration', 'change_registration')
        action_url = reverse(
            'team_registration_action',
            kwargs={'pk': self.registration.pk, 'action': 'paid'},
        )
        self.client.post(action_url)
        response = self.client.post(action_url, {
            'confirmed': 'true',
            'amount': '400000',
            'receipt_number': 'RCPT-100',
            'note': 'Paid at the office.',
        })
        self.assertRedirects(
            response,
            reverse(
                'team_registration_detail',
                kwargs={'pk': self.registration.pk},
            ),
        )
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.payment_status, 'paid')
        self.assertEqual(self.registration.amount_paid, 400000)
        self.assertIsNotNone(self.registration.paid_at)
        self.assertEqual(self.registration.payment_recorded_by, self.user.username)
        self.assertEqual(self.registration.receipt_number, 'RCPT-100')
        self.assertEqual(self.registration.payment_note, 'Paid at the office.')

    def test_part_payment_keeps_part_paid_status_and_tracks_the_amount(self):
        self.login_with('view_registration', 'change_registration')
        action_url = reverse(
            'team_registration_action',
            kwargs={'pk': self.registration.pk, 'action': 'part_paid'},
        )
        self.client.post(action_url)
        response = self.client.post(action_url, {
            'confirmed': 'true',
            'amount': '125000',
            'receipt_number': 'PART-1',
        })
        self.assertEqual(response.status_code, 302)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.payment_status, 'part_paid')
        self.assertEqual(self.registration.amount_paid, 125000)
        self.assertIsNotNone(self.registration.paid_at)
        self.assertEqual(self.registration.payment_recorded_by, self.user.username)

    def test_cancel_action_is_confirmed_and_records_the_user(self):
        self.login_with('view_registration', 'change_registration')
        action_url = reverse(
            'team_registration_action',
            kwargs={'pk': self.registration.pk, 'action': 'cancel'},
        )
        self.client.post(action_url)
        response = self.client.post(action_url, {'confirmed': 'true'})
        self.assertEqual(response.status_code, 302)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.payment_status, 'cancelled')
        self.assertIsNotNone(self.registration.paid_at)
        self.assertEqual(self.registration.payment_recorded_by, self.user.username)

    def test_registration_filters_and_search_work(self):
        self.login_with('view_registration')
        other = self.make_registration(
            parent_name='Another Parent',
            parent_email='another@example.com',
            learner_name='Other Learner',
            stage='discover',
            payment_method='online',
            receipt_number='ONLINE-22',
        )
        response = self.client.get(reverse('team_registrations'), {
            'stage': 'build',
            'method': 'cash',
        })
        self.assertContains(response, 'Learner Example')
        self.assertNotContains(response, 'Other Learner')
        response = self.client.get(reverse('team_registrations'), {
            'q': 'ONLINE-22',
        })
        self.assertContains(response, other.learner_name)
        self.assertNotContains(response, self.registration.learner_name)

    def test_empty_registration_and_message_lists_render(self):
        self.login_with('view_registration')
        self.registration.delete()
        self.contact_message.delete()
        response = self.client.get(reverse('team_registrations'))
        self.assertContains(response, 'No registrations found')
        self.grant(ContactMessage, 'view_contactmessage')
        response = self.client.get(reverse('team_messages'))
        self.assertContains(response, 'No messages here')

    def test_contact_messages_filter_and_toggle_follow_up(self):
        permissions = Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(ContactMessage),
            codename__in=('view_contactmessage', 'change_contactmessage'),
        )
        self.user.user_permissions.add(*permissions)
        self.client.force_login(self.user)
        response = self.client.get(reverse('team_messages'))
        self.assertContains(response, 'Parent Example')
        self.assertContains(response, 'wa.me/256700123456')
        response = self.client.post(
            reverse(
                'team_message_follow_up',
                kwargs={'pk': self.contact_message.pk},
            ),
            {'handled': 'true', 'follow_up': 'no'},
        )
        self.assertEqual(response.status_code, 302)
        self.contact_message.refresh_from_db()
        self.assertTrue(self.contact_message.handled)
        response = self.client.get(reverse('team_messages'), {'follow_up': 'yes'})
        self.assertContains(response, 'Mark as not followed up')
        response = self.client.post(
            reverse(
                'team_message_follow_up',
                kwargs={'pk': self.contact_message.pk},
            ),
            {'handled': 'false', 'follow_up': 'yes'},
        )
        self.assertEqual(response.status_code, 302)
        self.contact_message.refresh_from_db()
        self.assertFalse(self.contact_message.handled)

    def test_team_pages_have_noindex_and_no_cache_headers(self):
        self.login_with('view_registration')
        response = self.client.get(reverse('team_registrations'))
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, '<meta name="robots" content="noindex, nofollow">')
        self.assertNotContains(response, 'umami')
        self.assertContains(self.client.get('/robots.txt'), 'Disallow: /team/')

    def test_contact_email_has_team_link_and_registration_email_uses_team_detail(self):
        from .notifications import _build_text
        from .registration import _build_registration_text

        contact_body = _build_text(
            self.contact_message,
            'https://example.test/team/messages/',
        )
        registration_body = _build_registration_text(
            self.registration,
            'https://example.test/team/registrations/1/',
        )
        self.assertIn('https://example.test/team/messages/', contact_body)
        self.assertIn('https://example.test/team/registrations/1/', registration_body)
        self.assertNotIn('/admin/', contact_body)
        self.assertNotIn('/admin/', registration_body)

    def test_public_pages_do_not_link_to_the_team_area(self):
        self.client.force_login(self.user)
        public_urls = (
            '/', '/about/', '/contact/', '/join/', '/steam-experience/',
            '/for-schools/', '/partners/', '/global-opportunities/',
            '/innovators-circle/', '/impact/', '/shop/', '/privacy/',
            '/refund-policy/', '/share-your-story/', '/blog/',
        )
        for url in public_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertNotContains(response, 'href="/team/', msg_prefix=url)

    def test_team_forms_enforce_csrf(self):
        from django.test import Client

        self.login_with('view_registration', 'change_registration')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        action_url = reverse(
            'team_registration_action',
            kwargs={'pk': self.registration.pk, 'action': 'paid'},
        )
        response = client.post(action_url)
        self.assertEqual(response.status_code, 403)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('team_logout'))
        self.assertEqual(response.status_code, 405)
