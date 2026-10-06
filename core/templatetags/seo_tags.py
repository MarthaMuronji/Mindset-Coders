"""Template tags for search engine and analytics tags in the page head."""
import os

from django import template

register = template.Library()


@register.simple_tag
def canonical_url(request):
    """Absolute address of the current page, without any query string."""
    if not hasattr(request, 'build_absolute_uri'):
        return ''
    return request.build_absolute_uri(request.path)


@register.simple_tag
def umami_website_id():
    """Analytics website ID, empty when it is not configured on this machine."""
    return os.environ.get('UMAMI_WEBSITE_ID', '')
