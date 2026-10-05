from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """The main pages of the site, each addressed by its URL name."""

    def items(self):
        return [
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
            'contact',
        ]

    def location(self, item):
        return reverse(item)
