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
