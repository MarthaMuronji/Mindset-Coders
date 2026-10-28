from django.conf import settings

# Pages that must never carry the STEAM Experience promotion: the
# experience page itself, both ways of contacting the team, the privacy
# page, the story form, and the whole private review area (every url
# name that starts with "review"). The admin is checked separately
# because its url names are unrelated to the public site.
EXCLUDED_URL_NAMES = frozenset({
    'steam_experience',
    'contact',
    'privacy',
    'share_story',
})


def steam_promo(request):
    """Tell templates whether the corner chip may appear on this page.

    The Home view already passes steam_public for the announcement strip
    and the pop up, so this only adds the shared chip variables. The
    start date is the one fact the countdown wording is built from.
    """
    show = settings.STEAM_EXPERIENCE_PUBLIC
    if show:
        match = getattr(request, 'resolver_match', None)
        if match is None or match.namespace == 'admin':
            show = False
        else:
            name = match.url_name or ''
            if name in EXCLUDED_URL_NAMES or name.startswith('review'):
                show = False
    return {'steam_promo': show, 'steam_start_date': '2026-11-16'}
