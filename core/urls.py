from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('mindset-learn/', views.mindset_learn, name='mindset_learn'),
    path('about/', views.about, name='about'),
    path('programs/', views.programs, name='programs'),
    path('contact/', views.contact, name='contact'),
    path('competitions/', views.competitions, name='competitions'),
    path('for-schools/', views.for_schools, name='for_schools'),
    path('for-educators/', views.for_educators, name='for_educators'),
    path('events/', views.events, name='events'),
    path('for-learners/', views.for_learners, name='for_learners'),
    path('partners/', views.partners, name='partners'),
    path('resources/', views.resources, name='resources'),
    path('blog/', views.blog, name='blog'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)