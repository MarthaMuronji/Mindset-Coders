"""The Join page: one short registration form for parents and guardians.

The form, the two views and the team notification all live here, so the
Contact and Story pages keep working exactly as they did. Nothing on this
page takes a payment, and the page renders without a database.
"""
import json
import logging
import os
import urllib.error
import urllib.request
from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from . import views
from .models import Registration
from .notifications import BREVO_SEND_URL, TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# The programme values the team shares as links. Only these preselect a
# programme when the page is opened with ?programme= in the address.
PRESELECTABLE_PROGRAMMES = ('holiday', 'weekend', 'school')

# The stage values the team shares as links, taken from the model itself,
# so they can never drift apart. Only these preselect a stage when the
# page is opened with ?stage= in the address.
PRESELECTABLE_STAGES = tuple(
    value for value, _label in Registration.STAGE_CHOICES
)

# Shown on the Join page when saving fails, so the visitor can retry
SAVE_FAILED_MESSAGE = 'Sorry, we could not send your registration. Please try again in a moment.'


class RegistrationForm(forms.ModelForm):
    """The Join form.

    The honeypot field is declared but never listed in Meta.fields, so what
    a bot types into it can never reach the model, and there is no file
    field anywhere, so nothing can be uploaded.
    """

    # The model-derived checkbox would come out as required=False (Django
    # allows unchecked boxes), so consent is declared here to be a real
    # required checkbox
    consent = forms.BooleanField(
        required=True,
        label='I am the parent or guardian of this learner, and I agree to Mindset Coders contacting me about this registration.',
        error_messages={
            'required': 'Please tick this box so we can contact you about this registration.',
        },
    )

    # A whole number between 3 and 25, with a friendly message instead of
    # Django's "Ensure this value is ...". The label lives here too, because
    # a declared field does not take its label from Meta.
    learner_age = forms.IntegerField(
        min_value=3,
        max_value=25,
        label="Learner's age",
        error_messages={
            'invalid': 'Please enter a whole number for the age, between 3 and 25.',
            'min_value': 'Please enter an age between 3 and 25.',
            'max_value': 'Please enter an age between 3 and 25.',
        },
    )

    # Spam trap, rendered hidden by the .honeypot-field wrapper in the template
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'tabindex': '-1',
            'autocomplete': 'off',
        }),
    )

    # The stage belongs to the Holiday STEAM Experience only, so the
    # field itself is never required on its own. clean() below asks for
    # it when the programme is holiday, and clears it for every other
    # programme, which keeps one rule in one place.
    stage = forms.ChoiceField(
        choices=Registration.STAGE_CHOICES,
        required=False,
        label='Stage',
        help_text='Choose a stage if you picked the Holiday STEAM Experience.',
    )

    class Meta:
        model = Registration
        # consent and learner_age are declared above but stay in the field
        # list, so their answers still reach the model. The honeypot is left
        # out on purpose, and created_at and handled belong to the admin.
        fields = (
            'parent_name', 'parent_email', 'parent_phone', 'learner_name',
            'learner_age', 'school_name', 'programme', 'stage', 'consent',
        )
        labels = {
            'parent_name': 'Your name',
            'parent_email': 'Your email',
            'parent_phone': 'Your phone number',
            'learner_name': "Learner's name",
            'school_name': 'School (optional)',
            'programme': 'Programme',
        }

    def clean(self):
        cleaned_data = super().clean()
        programme = cleaned_data.get('programme')
        if programme == 'holiday':
            if not cleaned_data.get('stage'):
                self.add_error(
                    'stage',
                    'Please choose a stage for the Holiday STEAM Experience.',
                )
        else:
            # The stage only describes the Holiday STEAM Experience, so
            # any other programme stores it empty
            cleaned_data['stage'] = ''
        return cleaned_data


def _build_registration_text(registration, admin_url):
    """One line of plain text for one saved registration.

    The team can open the entry in the admin, so the email itself never
    needs a name, an age, a phone number or an address.
    """
    return 'A new registration was received for the {}. Open it here: {}'.format(
        registration.get_programme_display(),
        admin_url,
    )


def send_registration_notification(registration, admin_url):
    """Email the team about one saved registration. Never raises.

    The same Brevo helper pattern as the Contact form: without the three
    environment variables the feature is off, so local development needs no
    setup, and every problem is logged as a short warning.
    """
    api_key = os.environ.get('BREVO_API_KEY')
    notify_raw = os.environ.get('CONTACT_NOTIFY_EMAIL')
    from_email = os.environ.get('CONTACT_FROM_EMAIL')
    recipients = [a.strip() for a in notify_raw.split(',') if a.strip()] if notify_raw else []

    # Without these three the feature is off, so local development needs no setup
    if not api_key or not recipients or not from_email:
        return

    try:
        payload = {
            'sender': {
                'name': os.environ.get('CONTACT_FROM_NAME', 'Mindset Coders Website'),
                'email': from_email,
            },
            'to': [{'email': address} for address in recipients],
            # No reply-to on purpose: the email carries no personal
            # details, so a reply could never reach the parent
            'subject': 'New registration received',
            'textContent': _build_registration_text(registration, admin_url),
        }
        request = urllib.request.Request(
            BREVO_SEND_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'api-key': api_key,
                'content-type': 'application/json',
                'accept': 'application/json',
            },
            method='POST',
        )
        response = urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
        try:
            response.read()
        finally:
            response.close()
    except urllib.error.HTTPError as exc:
        # Log only the status, never the api key or the registration details
        logger.warning('Registration notification email failed with HTTP status %s', exc.code)
    except Exception as exc:
        logger.warning('Registration notification email failed (%s)', type(exc).__name__)


def join(request):
    """The Join page: one short form, saved so the team can read it."""
    if request.method == 'POST':
        # Spam trap: humans never see this field, so pretend it worked
        # and store nothing at all
        if request.POST.get('website', '').strip():
            return redirect('join_thanks')
        form = RegistrationForm(request.POST)
        if form.is_valid():
            # Keep the registration so the team can read it and mark it handled
            try:
                registration = form.save()
            except Exception:
                # Saving failed, so keep the typed input and ask to retry
                messages.error(request, SAVE_FAILED_MESSAGE)
            else:
                # Notify the team, but never let the email change the outcome above
                change_url = reverse(
                    'admin:core_registration_change', args=[registration.pk]
                )
                admin_url = request.build_absolute_uri(change_url)
                try:
                    send_registration_notification(registration, admin_url)
                except Exception:
                    logger.exception('Failed to send registration notification')
                # Only the programme and the stage travel in the address,
                # so no name, age or contact detail ever lands in a link
                query = urlencode({
                    'programme': registration.programme,
                    'stage': registration.stage,
                })
                return redirect('{}?{}'.format(reverse('join_thanks'), query))
    else:
        programme = request.GET.get('programme', '')
        stage = request.GET.get('stage', '')
        initial = {}
        if programme in PRESELECTABLE_PROGRAMMES:
            # Only ever preselect a programme the form actually offers
            initial['programme'] = programme
        if stage in PRESELECTABLE_STAGES:
            # Only ever preselect a stage the form actually offers
            initial['stage'] = stage
        form = RegistrationForm(initial=initial)
    return render(request, 'join.html', {'form': form})


def join_thanks(request):
    """The page shown after a registration has been stored.

    The Holiday STEAM Experience registration shows its payment button
    only when the stage is one of ours and payments are switched on. The
    matching link comes from the STEAM Experience dictionary, whose
    entries carry a key for each stage. Every other registration lands
    on the plain thank you page.
    """
    programme = request.GET.get('programme', '')
    stage = request.GET.get('stage', '')
    stage_labels = dict(Registration.STAGE_CHOICES)
    stage_label = stage_labels.get(stage, '')
    payment_link = None
    if (
        programme == 'holiday'
        and stage_label
        and settings.STEAM_PAYMENTS_ENABLED
    ):
        for link in views.STEAM_EXPERIENCE.get('payment_links', []):
            if link.get('key') == stage:
                payment_link = link
                break
    return render(request, 'join_thanks.html', {
        # The button to the STEAM Experience page only appears once that
        # page is public, the same rule the rest of the site follows
        'steam_public': settings.STEAM_EXPERIENCE_PUBLIC,
        'programme': programme,
        'stage_label': stage_label,
        'payment_link': payment_link,
    })
