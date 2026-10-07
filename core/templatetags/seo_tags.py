"""Template tags for search engine and analytics tags in the page head."""
import os

from django import template
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def canonical_url(request):
    """Absolute address of the current page, without any query string."""
    if not hasattr(request, 'build_absolute_uri'):
        return ''
    return request.build_absolute_uri(request.path)


@register.simple_tag
def static_absolute_url(request, path):
    """Absolute address of a static file for the current request."""
    if not hasattr(request, 'build_absolute_uri'):
        return ''
    url = request.build_absolute_uri(static(path))
    host = request.get_host().partition(':')[0]
    if host not in ('localhost', '127.0.0.1') and url.startswith('http://'):
        url = 'https://' + url[len('http://'):]
    return url


@register.simple_tag
def umami_website_id():
    """Analytics website ID, empty when it is not configured on this machine."""
    return os.environ.get('UMAMI_WEBSITE_ID', '')
