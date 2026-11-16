import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from core.team_people import create_command_invitee, resend_command_invitee
from core.notifications import send_team_invite


class Command(BaseCommand):
    help = (
        'Create a team account and print its one-time invitation link. '
        'With --resend, reissue the link for an existing team member who has not set a password yet.'
    )

    def add_arguments(self, parser):
        parser.add_argument('full_name')
        parser.add_argument('email')
        parser.add_argument('role')
        parser.add_argument(
            '--resend',
            action='store_true',
            help=(
                'Reissue the invite link when a person with this email already exists '
                'as a team member without a password. The name and role are then ignored.'
            ),
        )

    def handle(self, *args, **options):
        try:
            if options['resend']:
                user, path = resend_command_invitee(options['email'])
            else:
                user, path = create_command_invitee(
                    options['full_name'],
                    options['email'],
                    options['role'],
                )
        except ValidationError as error:
            raise CommandError('; '.join(error.messages)) from error
        base_url = os.environ.get('TEAM_BASE_URL', '').strip().rstrip('/')
        if not base_url:
            base_url = getattr(settings, 'TEAM_BASE_URL', '').strip().rstrip('/')
        invite_url = '{}{}'.format(base_url, path) if base_url else path
        if base_url:
            send_team_invite(user.email, invite_url)
        self.stdout.write(invite_url)
