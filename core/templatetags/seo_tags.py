"""Template tags for search engine tags in the page head."""
from django import template

register = template.Library()


@register.simple_tag
def canonical_url(request):
    """Absolute address of the current page, without any query string."""
    if not hasattr(request, 'build_absolute_uri'):
        return ''
    return request.build_absolute_uri(request.path)
