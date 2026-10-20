import logging
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import ContactForm, ReviewStoryForm, StoryForm
from .models import ContactMessage, Post, Story
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

# Shown only after a story has been stored, or after the spam trap has
# silently swallowed the submission
STORY_SUCCESS_MESSAGE = 'Thank you for sharing your story. We will read it and may contact you before anything is published.'


# Create your views here.
def home(request):
    return render(request, 'home.html')

def mindset_learn(request):
    return render(request, 'mindset_learn.html')

def about(request):
    return render(request, 'about.html')

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
                    logger.exception("Failed to send contact notification")
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

def global_opportunities(request):
    return render(request, 'global_opportunities.html')

def for_schools(request):
    return render(request, 'for_schools.html')

def partners(request):
    return render(request, 'partners.html')

def innovators_circle(request):
    return render(request, 'innovators_circle.html')

def university_preparation(request):
    return render(request, 'university_preparation.html')

# Shop page products: adding one entry here adds one product tile on the page.
PRODUCTS = [
    {'name': "Byte's World / Coding Unplugged"},
    {'name': 'Byte Thinks / AI Unplugged'},
    {'name': 'RoboBOX'},
    {'name': 'Robotics kits'},
    {'name': 'STEAM learning kits'},
    {'name': 'Teacher resources'},
    {'name': 'Mission cards and other learning resources'},
]

def shop(request):
    return render(request, 'shop.html', {'products': PRODUCTS})

def impact(request):
    """The impact page, with approved stories grouped by category."""
    stories_by_category = {key: [] for key, _label in Story.CATEGORY_CHOICES}
    try:
        # Evaluated inside the try, so an unreachable database leaves the
        # page rendering with the empty state instead of a server error
        approved_stories = list(Story.objects.filter(approved=True).order_by('-created_at'))
    except (DatabaseError, ImproperlyConfigured):
        logger.exception('Approved stories could not be read for the impact page')
        approved_stories = []
    for story in approved_stories:
        if story.category in stories_by_category:
            stories_by_category[story.category].append(story)
    return render(request, 'impact.html', {'stories_by_category': stories_by_category})

def share_story(request):
    if request.method == 'POST':
        # Spam trap: humans never see this field, so pretend it worked
        # and store nothing at all
        if request.POST.get('website', '').strip():
            messages.success(request, STORY_SUCCESS_MESSAGE)
            return redirect('share_story')
        form = StoryForm(request.POST)
        if form.is_valid():
            # Keep the story so the team can read it and approve it in the admin
            try:
                story = form.save()
            except Exception:
                # Saving failed, so keep the typed text and ask to retry
                messages.error(request, "Sorry, we could not send your story. Please try again in a moment.")
            else:
                # Notify the team, but never let the email change the outcome above
                admin_url = request.build_absolute_uri('/admin/core/story/')
                review_url = request.build_absolute_uri('/review/')
                try:
                    send_contact_notification(story, admin_url, review_url)
                except Exception:
                    logger.exception("Failed to send story notification")
                messages.success(request, STORY_SUCCESS_MESSAGE)
                return redirect('share_story')
    else:
        form = StoryForm()
    return render(request, 'share_story.html', {'form': form})


# ---------------------------------------------------------------------------
# Private team area for reviewing the stories people send in.
#
# Nothing here is linked from the public site, every response asks search
# engines not to index it, and only an active account with the
# core.change_story permission may see a story.

REVIEW_TABS = ('waiting', 'published', 'rejected')

# The login throttle: after this many wrong tries, one IP address and
# username pair waits LOGIN_ATTEMPT_WINDOW seconds before trying again
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW = 15 * 60
LOGIN_ATTEMPT_MESSAGE = 'Too many tries. Please wait 15 minutes and try again.'


def review_page(view):
    """Keep the team pages private: never cached, never indexed."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
    return never_cache(wrapper)


def _reviewer_has_access(user):
    """Only an active account with the review permission sees stories."""
    return user.is_authenticated and user.is_active and user.has_perm('core.change_story')


def _review_login_url(next_url):
    """The login page with an explicit next parameter."""
    return '{}?{}'.format(reverse('review_login'), urlencode({'next': next_url}))


def _denied_or_login(request):
    """A friendly no for signed in accounts, the login page for everyone else."""
    if request.user.is_authenticated:
        return render(request, '403.html', {'hide_umami': True}, status=403)
    return redirect(_review_login_url(request.get_full_path()))


class ReviewLoginForm(AuthenticationForm):
    """The team login form, with this site's wording for a wrong try."""

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'That username and password did not match. Please try again.',
    }


def _login_throttle_key(request):
    """One counter for each IP address and username pair."""
    username = request.POST.get('username', '').strip().lower()
    return 'review-login:{}:{}'.format(request.META.get('REMOTE_ADDR', ''), username)


@method_decorator(review_page, name='dispatch')
class ReviewLoginView(LoginView):
    template_name = 'review/login.html'
    authentication_form = ReviewLoginForm
    redirect_authenticated_user = True
    # A login that arrives without a next parameter still lands on the list
    next_page = reverse_lazy('review_list')

    def post(self, request, *args, **kwargs):
        # Too many recent tries: show the message and never check the password
        if cache.get(_login_throttle_key(request), 0) >= LOGIN_ATTEMPT_LIMIT:
            # An unbound form only echoes what was typed, so this request
            # never reaches the password check
            form = self.get_form_class()(initial={'username': request.POST.get('username', '')})
            return self.render_to_response(
                self.get_context_data(form=form, throttle_message=LOGIN_ATTEMPT_MESSAGE)
            )
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        # Count this failed try against the IP address and username pair
        key = _login_throttle_key(self.request)
        cache.set(key, cache.get(key, 0) + 1, LOGIN_ATTEMPT_WINDOW)
        return super().form_invalid(form)

    def form_valid(self, form):
        # A correct login clears the counter, so normal logins never break
        cache.delete(_login_throttle_key(self.request))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_umami'] = True
        return context


# Django's LogoutView answers any GET with 405, so only POST can log out
review_logout = review_page(LogoutView.as_view(next_page=reverse_lazy('review_login')))


@method_decorator(review_page, name='dispatch')
class ReviewPasswordChangeView(PasswordChangeView):
    """Let a signed in team member change their own password."""
    template_name = 'review/password_change.html'
    # A finished change lands back on the review list
    success_url = reverse_lazy('review_list')

    def dispatch(self, request, *args, **kwargs):
        # Only a signed in account gets here, sent by an explicit login url
        if not request.user.is_authenticated:
            return redirect('{}?{}'.format(
                reverse('review_login'), urlencode({'next': request.get_full_path()})
            ))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Your password has been changed.')
        # super() saves, keeps this session signed in and redirects
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_umami'] = True
        return context


def _stories_for_tab(tab):
    if tab == 'published':
        return Story.objects.filter(approved=True)
    if tab == 'rejected':
        return Story.objects.filter(rejected=True)
    return Story.objects.filter(approved=False, rejected=False)


def _review_list_context(tab):
    """Everything the review list template needs for one tab."""
    stories = list(_stories_for_tab(tab))
    for story in stories:
        # One editable form per card; the auto_id keeps every id unique
        story.edit_form = ReviewStoryForm(instance=story, auto_id='story{}-id_%s'.format(story.pk))
    return {
        'tab': tab,
        'stories': stories,
        'counts': {
            'waiting': Story.objects.filter(approved=False, rejected=False).count(),
            'published': Story.objects.filter(approved=True).count(),
            'rejected': Story.objects.filter(rejected=True).count(),
        },
        'show_help': tab == 'waiting',
        'hide_umami': True,
    }


@review_page
def review_list(request):
    if not _reviewer_has_access(request.user):
        return _denied_or_login(request)
    tab = request.GET.get('tab', 'waiting')
    if tab not in REVIEW_TABS:
        tab = 'waiting'
    return render(request, 'review/list.html', _review_list_context(tab))


@review_page
@require_POST
def review_action(request, pk):
    """Every change to a story happens here, by POST, and never by GET."""
    if not _reviewer_has_access(request.user):
        if request.user.is_authenticated:
            return render(request, '403.html', {'hide_umami': True}, status=403)
        return redirect(_review_login_url(reverse('review_list')))

    story = get_object_or_404(Story, pk=pk)
    action = request.POST.get('action', '')
    tab = request.GET.get('tab', 'waiting')
    if tab not in REVIEW_TABS:
        tab = 'waiting'
    list_url = '{}?tab={}'.format(reverse('review_list'), tab)

    if action in ('save', 'publish'):
        # Edits are validated exactly like the share form validates them
        form = ReviewStoryForm(request.POST, instance=story)
        if not form.is_valid():
            # Show the same card again with the problems marked on it
            context = _review_list_context(tab)
            for item in context['stories']:
                if item.pk == story.pk:
                    item.edit_form = form
            return render(request, 'review/list.html', context)
        story = form.save(commit=False)
        if action == 'publish':
            story.approved = True
            story.rejected = False
            story.reviewed_at = timezone.now()
            story.reviewed_by = request.user
            story.save()
            messages.success(request, 'Story published. It is now on the Impact page.')
        else:
            story.save()
            messages.success(request, 'Changes saved.')
    elif action == 'reject':
        story.approved = False
        story.rejected = True
        story.reviewed_at = timezone.now()
        story.reviewed_by = request.user
        story.save(update_fields=['approved', 'rejected', 'reviewed_at', 'reviewed_by'])
        messages.success(request, 'Story marked as not published.')
    elif action == 'take_down':
        story.approved = False
        story.rejected = False
        story.save(update_fields=['approved', 'rejected'])
        messages.success(request, 'Story taken down.')
    elif action == 'waiting':
        story.rejected = False
        story.save(update_fields=['rejected'])
        messages.success(request, 'Story moved back to waiting.')
    else:
        # An unknown action changes nothing
        raise Http404
    return redirect(list_url)

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
        'Disallow: /review/',
        'Sitemap: {}'.format(request.build_absolute_uri('/sitemap.xml')),
    ]
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain')