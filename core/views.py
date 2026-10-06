import logging

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ContactForm
from .models import ContactMessage, Post
from .notifications import send_contact_notification

logger = logging.getLogger(__name__)

# Starting text for the message box when someone arrives from a route card.
# Any other topic value is ignored, and the value is never printed anywhere.
TOPIC_STARTERS = {
    'learner': 'I am interested in Mindset Learn.',
    'school': 'I would like to bring STEAM to our school.',
    'global': 'I would like to know more about global opportunities.',
    'university': 'I would like to know more about University Preparation.',
    'products': 'I would like to know more about your products and resources.',
    'partner': 'I would like to partner with Mindset Coders.',
    'story': 'I would like to share a story with Mindset Coders.',
    'fund': "I would like to fund a young innovator through the Innovators' Circle.",
    'equip': "I would like to equip a young innovator through the Innovators' Circle.",
    'mentor': "I would like to mentor a young innovator through the Innovators' Circle.",
    'circle-partner': "I would like to partner with the Innovators' Circle.",
}


# Create your views here.
def home(request):
    return render(request, 'home.html')

def mindset_learn(request):
    return render(request, 'mindset_learn.html')

def about(request):
    return render(request, 'about.html')

def programs(request):
    return render(request, 'programs.html')

def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Keep the message so the team can read it and mark it handled in the admin
            try:
                contact_message = ContactMessage.objects.create(
                    name=form.cleaned_data['name'],
                    email=form.cleaned_data['email'],
                    role=form.cleaned_data['role'],
                    message=form.cleaned_data['message'],
                )
            except Exception:
                # Saving failed, so keep the typed input and ask the sender to retry
                messages.error(request, "Sorry, we could not send your message. Please try again in a moment.")
            else:
                # Notify the team, but never let the email change the outcome above
                admin_url = request.build_absolute_uri('/admin/core/contactmessage/')
                try:
                    send_contact_notification(contact_message, admin_url)
                except Exception:
                    pass
                messages.success(request, "Thanks for reaching out! We'll be in touch soon.")
                return redirect('contact')
    else:
        starter = TOPIC_STARTERS.get(request.GET.get('topic', ''))
        initial = {}
        if starter and 'message' in ContactForm.base_fields:
            # Only ever pre-fill an empty message box
            initial = {'message': starter}
        form = ContactForm(initial=initial)
    return render(request, 'contact.html', {'form': form})

def competitions(request):
    return render(request, 'competitions.html')

def global_opportunities(request):
    return render(request, 'global_opportunities.html')

def for_schools(request):
    return render(request, 'for_schools.html')

def for_educators(request):
    return render(request, 'for_educators.html')

def events(request):
    return render(request, 'events.html')

def resources(request):
    return render(request, 'resources.html')

def for_learners(request):
    return render(request, 'for_learners.html')

def partners(request):
    return render(request, 'partners.html')

def innovators_circle(request):
    return render(request, 'innovators_circle.html')

def university_preparation(request):
    return render(request, 'university_preparation.html')

# Shop page products: adding one entry here adds one product tile on the page.
PRODUCTS = [
    {'name': "Byte's World / Coding Unplugged"},
    {'name': 'Byte Thinks'},
    {'name': 'RoboBOX'},
    {'name': 'Robotics kits'},
    {'name': 'STEAM learning kits'},
    {'name': 'Teacher resources'},
    {'name': 'Mission cards and other learning resources'},
]

def shop(request):
    return render(request, 'shop.html', {'products': PRODUCTS})

def impact(request):
    return render(request, 'impact.html')

def blog(request):
    posts = Post.objects.filter(published=True)
    return render(request, 'blog.html', {'posts': posts})

def blog_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, published=True)
    return render(request, 'blog_detail.html', {'post': post})

def robots_txt(request):
    """robots.txt rules, with the sitemap address for this host."""
    lines = [
        'User-agent: *',
        'Disallow: /admin/',
        'Sitemap: {}'.format(request.build_absolute_uri('/sitemap.xml')),
    ]
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain')