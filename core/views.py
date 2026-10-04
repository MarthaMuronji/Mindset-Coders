from django.shortcuts import render, get_object_or_404
from .models import Post
from django.contrib import messages
from django.shortcuts import redirect
from .forms import ContactForm


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
        form = ContactForm()
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

def blog(request):
    posts = Post.objects.filter(published=True)
    return render(request, 'blog.html', {'posts': posts})

def blog_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, published=True)
    return render(request, 'blog_detail.html', {'post': post})