"""Send a plain text notification email through Brevo's HTTPS API.

Only the Python standard library is used here, so no package is added to
requirements.txt. Sending is best effort: every problem is logged as a short
warning and the function always returns quietly.
"""
import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

BREVO_SEND_URL = 'https://api.brevo.com/v3/smtp/email'
SUBJECT = 'New message from the Mindset Coders website'
TIMEOUT_SECONDS = 8


def _build_text(contact_message, admin_url):
    """Plain text body for one saved contact message."""
    lines = [
        'You have a new message from the website contact form.',
        '',
        'Name: {}'.format(contact_message.name),
        'Email: {}'.format(contact_message.email),
    ]
    # Only mention the role when the model actually has that field
    if hasattr(contact_message, 'role'):
        lines.append('Role: {}'.format(contact_message.role))
    lines.append('Sent: {}'.format(getattr(contact_message, 'created_at', None)))
    lines.extend([
        '',
        'Message:',
        str(getattr(contact_message, 'message', '')),
        '',
        'All messages are in the admin: {}'.format(admin_url),
    ])
    return '\n'.join(lines)


def send_contact_notification(contact_message, admin_url):
    """Email the team about one saved contact message. Never raises."""
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
            'replyTo': {
                'email': contact_message.email,
                'name': contact_message.name,
            },
            'subject': SUBJECT,
            'textContent': _build_text(contact_message, admin_url),
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
        # Log only the status, never the api key or the message content
        logger.warning('Contact notification email failed with HTTP status %s', exc.code)
    except Exception as exc:
        logger.warning('Contact notification email failed (%s)', type(exc).__name__)
