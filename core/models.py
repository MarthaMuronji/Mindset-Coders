from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.CharField(max_length=300, help_text="Short summary shown on the blog list page")
    content = models.TextField()
    cover_image = models.ImageField(upload_to='blog/', blank=True, null=True)
    author = models.CharField(max_length=100, default="Mindset Coders Team")
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class Story(models.Model):
    """A story sent through the Share your story form, reviewed in the admin.

    name and email are private: they are only used to reply to the writer
    and are never shown on the website. Only approved stories are shown, and
    the public sees the name exactly the way display_as allows.
    """

    ROLE_CHOICES = [
        ('learner', 'Learner'),
        ('parent', 'Parent or guardian'),
        ('teacher', 'Teacher'),
        ('school', 'School'),
        ('partner', 'Partner'),
        ('other', 'Other'),
    ]

    # The four story categories shown on the Impact and Stories page
    CATEGORY_CHOICES = [
        ('learner', 'Learner stories'),
        ('school', 'School stories'),
        ('teacher', 'Teacher stories'),
        ('competition', 'Competition stories'),
    ]

    DISPLAY_CHOICES = [
        ('anonymous', 'Anonymous'),
        ('first_name', 'First name only'),
        ('full_name', 'Full name'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    story = models.TextField(max_length=2000)
    display_as = models.CharField(max_length=20, choices=DISPLAY_CHOICES, default='anonymous')
    consent = models.BooleanField()
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # Review state: a story is waiting while both approved and rejected are False
    rejected = models.BooleanField(default=False)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_stories',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def display_name(self):
        """The name shown on the website, exactly as the writer chose it."""
        if self.display_as == 'first_name':
            parts = self.name.split()
            return parts[0] if parts else 'Anonymous'
        if self.display_as == 'full_name':
            return self.name
        return 'Anonymous'


class Registration(models.Model):
    """A parent's registration for a Mindset Coders programme.

    It arrives through the Join form, is read in the admin, and is never
    shown on the website.
    """

    # The four ways a family can describe the programme they are interested in
    PROGRAMME_CHOICES = [
        ('holiday', 'Holiday STEAM Experience'),
        ('weekend', 'Weekend classes'),
        ('school', 'Through a participating school'),
        ('unsure', 'Not sure yet'),
    ]

    # The four stages of the Holiday STEAM Experience. A stage only ever
    # belongs to that programme, so the field stays blank for the others.
    STAGE_CHOICES = [
        ('discover', 'Discover (2 weeks)'),
        ('build', 'Build (3 weeks)'),
        ('innovate', 'Innovate (4 weeks)'),
        ('full', 'Full journey (paid upfront)'),
    ]

    parent_name = models.CharField(max_length=100)
    parent_email = models.EmailField()
    parent_phone = models.CharField(max_length=30)
    learner_name = models.CharField(max_length=100)
    learner_age = models.PositiveSmallIntegerField()
    school_name = models.CharField(max_length=200, blank=True)
    programme = models.CharField(max_length=20, choices=PROGRAMME_CHOICES)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, blank=True)
    consent = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.learner_name} ({self.parent_name})'


class ContactMessage(models.Model):
    """A message sent through the contact form, shown in the Django admin."""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    role = models.CharField(max_length=20)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.email})'
