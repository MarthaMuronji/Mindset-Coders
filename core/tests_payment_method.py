from unittest import mock

from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import timezone

from . import admin as core_admin
from . import views
from .models import Registration
from .registration import STAGE_FEES


VALID_POST = {
    'parent_name': 'Test Parent',
    'parent_email': 'parent@example.com',
    'parent_phone': '+256 700 000000',
    'learner_name': 'Test Learner',
    'learner_age': '10',
    'school_name': '',
    'programme': 'holiday',
    'stage': 'discover',
    'payment_method': 'online',
    'consent': 'on',
    'website': '',
}


@override_settings(STEAM_PAYMENTS_ENABLED=True)
class PaymentMethodTests(SimpleTestCase):
    def submit(self, data, cash_instructions=None):
        saved = []

        def fake_save(registration, *args, **kwargs):
            registration.pk = 42
            saved.append(registration)

        instructions = (
            views.STEAM_EXPERIENCE['cash_instructions']
            if cash_instructions is None
            else cash_instructions
        )
        with mock.patch.dict(
            views.STEAM_EXPERIENCE, {'cash_instructions': instructions}
        ):
            with mock.patch.object(Registration, 'save', fake_save):
                with mock.patch(
                    'core.registration.send_registration_notification'
                ):
                    response = self.client.post('/join/', data)
        return response, saved

    def test_form_shows_required_payment_choice_and_hint_for_holiday(self):
        response = self.client.get('/join/?programme=holiday')

        self.assertContains(response, 'How will you pay?')
        self.assertContains(response, 'Pay online by Mobile Money')
        self.assertContains(response, 'Pay in cash')
        self.assertContains(
            response,
            'You can pay online straight after registering, or in cash during office hours.',
        )
        self.assertTrue(response.context['form'].fields['payment_method'].required)
        html = response.content.decode()
        self.assertLess(
            html.index('id="id_stage"'),
            html.index('id="id_payment_method_0"'),
        )

    def test_unselected_programme_starts_with_payment_choice_hidden(self):
        response = self.client.get('/join/')

        self.assertContains(response, 'id="payment-method-group" hidden')
        self.assertContains(response, "programme.addEventListener('change'")

    def test_cash_option_is_hidden_without_cash_instructions(self):
        with mock.patch.dict(
            views.STEAM_EXPERIENCE, {'cash_instructions': ''}
        ):
            response = self.client.get('/join/?programme=holiday')

        self.assertContains(response, 'Pay online by Mobile Money')
        self.assertNotContains(response, 'Pay in cash')
        self.assertEqual(
            response.context['form'].fields['payment_method'].choices,
            [('online', 'Pay online by Mobile Money')],
        )

    def test_cash_registration_redirects_to_cash_confirmation_without_payment_address(self):
        response, saved = self.submit(
            dict(VALID_POST, payment_method='cash')
        )

        self.assertEqual(
            response['Location'],
            '/join/thanks/?programme=holiday&stage=discover&method=cash',
        )
        self.assertEqual(saved[0].payment_method, 'cash')
        self.assertEqual(saved[0].amount_due, 300000)
        confirmation = self.client.get(response['Location'])
        html = confirmation.content.decode()
        self.assertContains(
            confirmation,
            'We have received your registration for the Holiday STEAM Experience, Discover (2 weeks).',
        )
        self.assertContains(confirmation, 'Amount to pay: UGX 300,000')
        self.assertContains(
            confirmation,
            'Your registration is confirmed once we receive your payment.',
        )
        self.assertContains(
            confirmation,
            views.STEAM_EXPERIENCE['cash_instructions'],
        )
        self.assertContains(
            confirmation,
            views.STEAM_EXPERIENCE['discount_note'],
        )
        self.assertContains(confirmation, 'Read our refund and cancellation policy')
        self.assertContains(confirmation, 'Register another child')
        self.assertNotIn('kacyberpay', html.lower())
        self.assertNotContains(confirmation, 'data-umami-event="pay-click"')
        self.assertNotContains(
            confirmation, 'You can also pay in cash. Contact our team to arrange it.'
        )

    def test_filled_cash_hold_note_only_shows_on_cash_confirmation(self):
        hold_note = 'Cash payment must be received before attendance.'
        with mock.patch.dict(
            views.STEAM_EXPERIENCE, {'cash_hold_note': hold_note}
        ):
            cash = self.client.get(
                '/join/thanks/?programme=holiday&stage=discover&method=cash'
            )
            online = self.client.get(
                '/join/thanks/?programme=holiday&stage=discover&method=online'
            )

        self.assertContains(cash, hold_note)
        self.assertNotContains(online, hold_note)

    def test_online_registration_shows_only_the_stage_payment_button(self):
        response, saved = self.submit(dict(VALID_POST, payment_method='online'))

        self.assertEqual(saved[0].payment_method, 'online')
        confirmation = self.client.get(response['Location'])
        self.assertContains(
            confirmation,
            'Pay UGX 300,000 with Mobile Money',
        )
        self.assertContains(
            confirmation,
            'href="https://kacyberpay.com/pay/f47mjrdxje"',
        )
        self.assertNotContains(confirmation, 'Pay the fee in cash at')

    def test_missing_payment_choice_fails_with_friendly_error(self):
        data = dict(VALID_POST)
        data.pop('payment_method')
        with mock.patch.object(Registration, 'save') as save_mock:
            response = self.client.post('/join/', data)

        save_mock.assert_not_called()
        self.assertContains(response, 'Please choose how you will pay.')

    def test_other_programmes_hide_and_do_not_save_payment_choice(self):
        data = dict(VALID_POST, programme='weekend')
        data.pop('stage')
        response, saved = self.submit(data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(saved[0].payment_method, '')
        self.assertIsNone(saved[0].amount_due)
        page = self.client.get('/join/?programme=weekend')
        self.assertNotContains(page, 'How will you pay?')

    @override_settings(STEAM_PAYMENTS_ENABLED=False)
    def test_payments_off_hide_and_do_not_save_payment_choice(self):
        response = self.client.get('/join/?programme=holiday')
        self.assertNotContains(response, 'How will you pay?')

        data = dict(VALID_POST)
        saved = []

        def fake_save(registration, *args, **kwargs):
            registration.pk = 42
            saved.append(registration)

        with mock.patch.object(Registration, 'save', fake_save):
            with mock.patch(
                'core.registration.send_registration_notification'
            ):
                posted = self.client.post('/join/', data)

        self.assertEqual(posted.status_code, 302)
        self.assertEqual(saved[0].payment_method, '')
        self.assertEqual(saved[0].amount_due, 300000)

    def test_amount_due_tracks_each_holiday_stage(self):
        for stage, amount in STAGE_FEES.items():
            with self.subTest(stage=stage):
                response, saved = self.submit(
                    dict(VALID_POST, stage=stage, payment_method='online')
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(saved[0].amount_due, amount)

    def test_fee_constant_matches_steam_payment_link_amounts(self):
        payment_link_fees = {
            entry['key']: int(
                entry['amount_text'].replace('UGX ', '').replace(',', '')
            )
            for entry in views.STEAM_EXPERIENCE['payment_links']
        }
        self.assertEqual(STAGE_FEES, payment_link_fees)

    def test_fee_constant_covers_all_registration_stages(self):
        self.assertEqual(
            set(STAGE_FEES),
            {key for key, _label in Registration.STAGE_CHOICES},
        )

    def test_registration_email_has_payment_lines_without_personal_details(self):
        from .registration import _build_registration_text

        registration = Registration(
            parent_name='Private Parent',
            parent_email='private@example.com',
            parent_phone='+256 700 000000',
            learner_name='Private Learner',
            learner_age=10,
            programme='holiday',
            stage='discover',
            payment_method='online',
            amount_due=300000,
            consent=True,
        )
        body = _build_registration_text(
            registration, 'https://example.test/admin/registration/1/'
        )

        self.assertIn('Payment method: Online', body)
        self.assertIn('Amount due: UGX 300000', body)
        for private_value in (
            'Private Parent',
            'private@example.com',
            '+256 700 000000',
            'Private Learner',
            '10',
        ):
            self.assertNotIn(private_value, body)

    def test_admin_payment_actions_and_old_registration_defaults(self):
        model_admin = core_admin.RegistrationAdmin(Registration, admin.site)
        now = timezone.now()
        request = RequestFactory().post('/admin/core/registration/')

        paid_queryset = mock.Mock()
        paid_queryset.exclude.return_value = paid_queryset
        paid_queryset.update.return_value = 1
        paid_queryset.count.return_value = 1
        with mock.patch.object(model_admin, 'message_user'):
            with mock.patch('core.admin.timezone.now', return_value=now):
                model_admin.mark_as_paid(request, paid_queryset)
        paid_queryset.update.assert_called_once_with(
            payment_status='paid',
            amount_paid=mock.ANY,
            paid_at=now,
        )
        self.assertEqual(
            paid_queryset.update.call_args.kwargs['amount_paid'].name,
            'amount_due',
        )

        cancelled_queryset = mock.Mock()
        cancelled_queryset.update.return_value = 1
        with mock.patch.object(model_admin, 'message_user'):
            model_admin.mark_as_cancelled(request, cancelled_queryset)
        cancelled_queryset.update.assert_called_once_with(
            payment_status='cancelled'
        )

        old_registration = Registration(
            parent_name='Old Parent',
            parent_email='old@example.com',
            parent_phone='',
            learner_name='Old Learner',
            learner_age=10,
            programme='holiday',
            stage='discover',
            consent=True,
        )
        self.assertEqual(old_registration.payment_method, '')
        self.assertEqual(old_registration.payment_status, 'pending')
        self.assertIsNone(old_registration.amount_due)
        self.assertEqual(model_admin.balance(old_registration), 0)
        fields = model_admin.get_fields(request, old_registration)
        for field in (
            'payment_method', 'payment_status', 'amount_due',
            'amount_paid', 'receipt_number', 'payment_note', 'paid_at',
            'balance',
        ):
            self.assertIn(field, fields)
