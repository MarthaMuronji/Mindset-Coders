from django.http import HttpResponsePermanentRedirect
from django.urls import path, reverse

from . import views
from django.conf import settings
from django.conf.urls.static import static


def _redirect_to(target_name, fragment=''):
    """Permanent redirect to another named route, built with reverse.

    The old page addresses now live inside the new pages, so each one
    hands the visitor straight to the section that replaced it.
    """
    def redirect_view(request):
        url = reverse(target_name)
        if fragment:
            url = '{}#{}'.format(url, fragment)
        return HttpResponsePermanentRedirect(url)
    return redirect_view


urlpatterns = [
    path('', views.home, name='home'),
    path('mindset-learn/', views.mindset_learn, name='mindset_learn'),
    path('about/', views.about, name='about'),
    path('programs/', _redirect_to('for_schools', 'programs'), name='programs'),
    path('contact/', views.contact, name='contact'),
    path('competitions/', _redirect_to('global_opportunities', 'how-competitions-work'), name='competitions'),
    path('global-opportunities/', views.global_opportunities, name='global_opportunities'),
    path('for-schools/', views.for_schools, name='for_schools'),
    path('for-educators/', _redirect_to('for_schools', 'teacher-training'), name='for_educators'),
    path('events/', _redirect_to('global_opportunities'), name='events'),
    path('for-learners/', _redirect_to('mindset_learn'), name='for_learners'),
    path('partners/', views.partners, name='partners'),
    path('innovators-circle/', views.innovators_circle, name='innovators_circle'),
    path('university-preparation/', views.university_preparation, name='university_preparation'),
    path('shop/', views.shop, name='shop'),
    path('impact/', views.impact, name='impact'),
    path('resources/', _redirect_to('shop'), name='resources'),
    path('blog/', views.blog, name='blog'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
