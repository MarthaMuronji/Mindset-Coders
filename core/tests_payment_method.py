import time
from unittest import mock

from django.contrib import admin
from django.core.signing import TimestampSigner
from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from . import admin as core_admin
from . import views
from .models import Registration
from .spam import FORM_TIMESTAMP_SALT
from .registration import STAGE_FEES


VALID_POST = {
    'parent_name': 'Test Parent',
    'parent_email': 'parent@example.com',
    'parent_phone': '+256 772 123 456',
    'learner_name': 'Test Learner',
    'learner_age': '10',
    'school_name': '',
    'programme': 'holiday',
    'stage': 'discover',
    'payment_method': 'online',
    'consent': 'on',
    'website': '',
    'form_timestamp': TimestampSigner(
        salt=FORM_TIMESTAMP_SALT
    ).sign(str(int(time.time()) - 4)),
}


class PaymentMethodTests(SimpleTestCase):
    def submit(self, data):
        saved = []

        def fake_save(registration, *args, **kwargs):
            registration.pk = 42
            saved.append(registration)

        with mock.patch.object(Registration, 'save', fake_save):
            with mock.patch(
                'core.registration.send_registration_notification'
            ):
                response = self.client.post('/join/', data)
        return response, saved

    def test_form_shows_required_payment_choice_and_hint_for_holiday(self):
        response = self.client.get('/join/?programme=holiday')

        self.assertContains(response, 'How will you pay?')
        self.assertContains(response, 'Mobile Money (*244*9#)')
        self.assertContains(response, 'Cash at the venue')
        self.assertTrue(response.context['form'].fields['payment_method'].required)
        self.assertEqual(
            response.context['form'].fields['payment_method'].choices,
            [
                ('online', 'Mobile Money (*244*9#)'),
                ('cash', 'Cash at the venue'),
            ],
        )
        html = response.content.decode()
        self.assertLess(
            html.index('id="id_stage"'),
            html.index('id="id_payment_method_0"'),
        )

    def test_unselected_programme_starts_with_payment_choice_hidden(self):
        response = self.client.get('/join/')

        self.assertContains(response, 'id="payment-method-group" hidden')
        self.assertContains(response, "programme.addEventListener('change'")

    def test_both_choices_remain_when_cash_instructions_are_empty(self):
        with mock.patch.dict(
            views.STEAM_EXPERIENCE, {'cash_instructions': ''}
        ):
            response = self.client.get('/join/?programme=holiday')

        self.assertContains(response, 'Mobile Money (*244*9#)')
        self.assertContains(response, 'Cash at the venue')
        self.assertEqual(
            response.context['form'].fields['payment_method'].choices,
            [
                ('online', 'Mobile Money (*244*9#)'),
                ('cash', 'Cash at the venue'),
            ],
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

    def test_mobile_money_registration_shows_instructions_without_a_button(self):
        response, saved = self.submit(dict(VALID_POST, payment_method='online'))

        self.assertEqual(saved[0].payment_method, 'online')
        confirmation = self.client.get(response['Location'])
        html = confirmation.content.decode()
        self.assertContains(
            confirmation,
            'Fee: UGX 300,000',
        )
        self.assertContains(
            confirmation,
            'To pay, dial *244*9#. Merchant code: 125730 (Mindset Coders Uganda).',
        )
        self.assertContains(
            confirmation,
            'Your registration is confirmed once we receive your payment.',
        )
        self.assertNotContains(confirmation, 'data-umami-event="pay-click"')
        self.assertNotContains(confirmation, 'Pay the fee in cash at')
        fee_position = html.index('Fee: UGX 300,000')
        instructions_position = html.index(
            'To pay, dial *244*9#. Merchant code: 125730 (Mindset Coders Uganda).'
        )
        confirmed_position = html.index(
            'Your registration is confirmed once we receive your payment.'
        )
        self.assertLess(fee_position, instructions_position)
        self.assertLess(instructions_position, confirmed_position)

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

    def test_amount_due_tracks_each_holiday_stage(self):
        for stage, amount in STAGE_FEES.items():
            with self.subTest(stage=stage):
                response, saved = self.submit(
                    dict(VALID_POST, stage=stage, payment_method='online')
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(saved[0].amount_due, amount)

    def test_fee_constant_keeps_the_current_stage_amounts(self):
        self.assertEqual(
            STAGE_FEES,
            {
                'discover': 300000,
                'build': 400000,
                'innovate': 500000,
                'full': 1100000,
            },
        )

    def test_fee_constant_covers_all_registration_stages(self):
        self.assertEqual(
            set(STAGE_FEES),
            {key for key, _label in Registration.STAGE_CHOICES},
        )

    def test_payment_method_display_labels_keep_the_existing_values(self):
        self.assertEqual(
            Registration.PAYMENT_METHOD_CHOICES,
            [('online', 'Online'), ('cash', 'Cash')],
        )
        self.assertEqual(
            Registration(payment_method='online').get_payment_method_display(),
            'Mobile Money (*244*9#)',
        )
        self.assertEqual(
            Registration(payment_method='cash').get_payment_method_display(),
            'Cash at the venue',
        )

    def test_registration_email_has_payment_lines_without_personal_details(self):
        from .registration import _build_registration_text

        registration = Registration(
            parent_name='Private Parent',
            parent_email='private@example.com',
            parent_phone='+256772123456',
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

        self.assertIn('Payment method: Mobile Money (*244*9#)', body)
        self.assertIn('Amount due: UGX 300000', body)
        for private_value in (
            'Private Parent',
            'private@example.com',
            '+256772123456',
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
        self.assertEqual(
            model_admin.payment_method_display(
                Registration(payment_method='cash')
            ),
            'Cash at the venue',
        )
        for field in (
            'payment_method_display', 'payment_status', 'amount_due',
            'amount_paid', 'receipt_number', 'payment_note', 'paid_at',
            'balance',
        ):
            self.assertIn(field, fields)
