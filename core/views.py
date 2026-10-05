from django.shortcuts import render, get_object_or_404
from .models import Post
from django.contrib import messages
from django.shortcuts import redirect
from .forms import ContactForm

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
            # For now, just confirm receipt — email sending wired up later
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