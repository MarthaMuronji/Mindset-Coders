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
