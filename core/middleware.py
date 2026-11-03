from django.conf import settings
from django.contrib import messages
from django.utils.cache import add_never_cache_headers


IDLE_SIGN_OUT_MESSAGE = (
    'You were signed out after a period of inactivity. Please sign in again.'
)
TEAM_SESSION_MARKER = 'team_session_seen'
TEAM_SESSION_MARKER_AGE = 30 * 24 * 60 * 60


class AdminResponseHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_prefix = '/{}/'.format(
            settings.ADMIN_URL_PATH.strip('/')
        )

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(self.admin_prefix):
            response['X-Robots-Tag'] = 'noindex, nofollow'
            add_never_cache_headers(response)
        return response


class TeamSessionExpiryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        team_request = request.path.startswith('/team/')
        login_or_logout = request.path in ('/team/login/', '/team/logout/')
        expired_session = (
            team_request
            and not login_or_logout
            and not request.user.is_authenticated
            and (
                TEAM_SESSION_MARKER in request.COOKIES
                or settings.SESSION_COOKIE_NAME in request.COOKIES
            )
        )
        if expired_session:
            messages.info(request, IDLE_SIGN_OUT_MESSAGE)

        response = self.get_response(request)

        if team_request:
            if request.path == '/team/logout/':
                response.delete_cookie(
                    TEAM_SESSION_MARKER,
                    path='/team/',
                    samesite='Lax',
                )
            elif request.user.is_authenticated:
                response.set_cookie(
                    TEAM_SESSION_MARKER,
                    '1',
                    max_age=TEAM_SESSION_MARKER_AGE,
                    path='/team/',
                    secure=not settings.DEBUG,
                    httponly=True,
                    samesite='Lax',
                )
            elif expired_session:
                response.delete_cookie(
                    TEAM_SESSION_MARKER,
                    path='/team/',
                    samesite='Lax',
                )
        return response
