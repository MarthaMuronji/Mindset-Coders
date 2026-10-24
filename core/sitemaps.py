from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """The main pages of the site, each addressed by its URL name."""

    def items(self):
        pages = [
            'home',
            'about',
            'mindset_learn',
            'for_schools',
            'global_opportunities',
            'innovators_circle',
            'university_preparation',
            'partners',
            'shop',
            'impact',
            'share_story',
            'contact',
        ]
        # The STEAM Experience page joins the sitemap only once it is public
        if getattr(settings, 'STEAM_EXPERIENCE_PUBLIC', False):
            pages.append('steam_experience')
        return pages

    def location(self, item):
        return reverse(item)
