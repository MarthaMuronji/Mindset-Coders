from django.http import HttpResponsePermanentRedirect
from django.urls import path, reverse

from . import registration
from . import team
from . import team_people
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
    # Mindset Learn now leads straight to the Join form, so the old address
    # keeps working as a permanent redirect for every link already out there
    path('mindset-learn/', _redirect_to('join'), name='mindset_learn'),
    path('join/', registration.join, name='join'),
    path('join/thanks/', registration.join_thanks, name='join_thanks'),
    path('about/', views.about, name='about'),
    path('programs/', _redirect_to('for_schools', 'programs'), name='programs'),
    path('contact/', views.contact, name='contact'),
    path('competitions/', _redirect_to('global_opportunities', 'how-competitions-work'), name='competitions'),
    path('global-opportunities/', views.global_opportunities, name='global_opportunities'),
    path('for-schools/', views.for_schools, name='for_schools'),
    path('for-educators/', _redirect_to('for_schools', 'teacher-training'), name='for_educators'),
    path('events/', _redirect_to('global_opportunities'), name='events'),
    path('for-learners/', _redirect_to('join'), name='for_learners'),
    path('partners/', views.partners, name='partners'),
    path('innovators-circle/', views.innovators_circle, name='innovators_circle'),
    path('university-preparation/', _redirect_to('home'), name='university_preparation'),
    path('privacy/', views.privacy, name='privacy'),
    path('refund-policy/', views.refund_policy, name='refund_policy'),
    path('shop/', views.shop, name='shop'),
    path('steam-experience/', views.steam_experience, name='steam_experience'),
    path('impact/', views.impact, name='impact'),
    path('share-your-story/', views.share_story, name='share_story'),
    path('review/', views.review_list, name='review_list'),
    path('review/login/', views.ReviewLoginView.as_view(), name='review_login'),
    path('review/logout/', views.review_logout, name='review_logout'),
    path('review/password/', views.ReviewPasswordChangeView.as_view(), name='review_password'),
    path('review/story/<int:pk>/', views.review_action, name='review_action'),
    path('resources/', _redirect_to('shop'), name='resources'),
    path('blog/', views.blog, name='blog'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('team/login/', team.TeamLoginView.as_view(), name='team_login'),
    path('team/logout/', team.team_logout, name='team_logout'),
    path('team/', team.team_home, name='team_home'),
    path('team/registrations/', team.registration_list, name='team_registrations'),
    path(
        'team/registrations/<int:pk>/',
        team.registration_detail,
        name='team_registration_detail',
    ),
    path(
        'team/registrations/<int:pk>/actions/<slug:action>/',
        team.registration_action,
        name='team_registration_action',
    ),
    path('team/messages/', team.message_list, name='team_messages'),
    path(
        'team/messages/<int:pk>/follow-up/',
        team.message_follow_up,
        name='team_message_follow_up',
    ),
    path('team/roster/', team.roster_list, name='team_roster'),
    path('team/roster/<int:pk>/', team.roster_detail, name='team_roster_detail'),
    path('team/people/', team_people.people_list, name='team_people'),
    path(
        'team/welcome/<uidb64>/<token>/',
        team_people.team_welcome,
        name='team_welcome',
    ),
    path('team/audit/', team_people.audit_log, name='team_audit'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
