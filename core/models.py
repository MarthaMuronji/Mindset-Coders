from django.conf import settings
from django.db import models
from django.db.models.signals import post_migrate
from django.dispatch import receiver
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

    PAYMENT_METHOD_CHOICES = [
        ('online', 'Online'),
        ('cash', 'Cash'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('part_paid', 'Part paid'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    parent_name = models.CharField(max_length=100)
    parent_email = models.EmailField()
    parent_phone = models.CharField(max_length=30)
    learner_name = models.CharField(max_length=100)
    learner_age = models.PositiveSmallIntegerField()
    school_name = models.CharField(max_length=200, blank=True)
    programme = models.CharField(max_length=20, choices=PROGRAMME_CHOICES)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, blank=True)
    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
    )
    amount_due = models.PositiveIntegerField(null=True, blank=True)
    amount_paid = models.PositiveIntegerField(default=0)
    receipt_number = models.CharField(max_length=100, blank=True)
    payment_note = models.TextField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_recorded_by = models.CharField(max_length=150, blank=True)
    consent = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        permissions = [
            ('view_full_registration', 'Can view full registration details'),
            ('view_finance_fields', 'Can view registration finance fields'),
            ('view_roster', 'Can view the learner roster'),
            ('reveal_contact', 'Can reveal parent contact details'),
            ('record_payment', 'Can record registration payments'),
            ('anonymise_registration', 'Can anonymise registrations'),
        ]

    def __str__(self):
        return f'{self.learner_name} ({self.parent_name})'


class ContactMessage(models.Model):
    """A message sent through the contact form, shown in the Django admin."""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    # Optional on the model, so older rows and older code keep working,
    # while the contact form itself always asks for it
    phone = models.CharField(max_length=30, null=True, blank=True)
    role = models.CharField(max_length=20)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.email})'


class AuditEvent(models.Model):
    ACTION_CHOICES = [
        ('sign_in', 'Signed in'),
        ('failed_sign_in', 'Failed sign in'),
        ('login_locked', 'Login temporarily locked'),
        ('registration_opened', 'Opened registration'),
        ('contact_revealed', 'Revealed parent contact'),
        ('payment_recorded', 'Recorded payment'),
        ('status_changed', 'Changed registration status'),
        ('anonymised', 'Anonymised registration'),
        ('invite_sent', 'Created invitation link'),
        ('role_changed', 'Changed team role'),
        ('person_switched_off', 'Switched off team member'),
        ('person_switched_on', 'Switched on team member'),
        ('message_followed_up', 'Marked message followed up'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='team_audit_events',
    )
    username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    detail = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        permissions = [
            ('manage_team', 'Can manage team members'),
            ('view_audit_log', 'Can view the team audit log'),
        ]
        indexes = [models.Index(fields=['-created_at', '-id'])]

    def __str__(self):
        return '{}: {}'.format(self.get_action_display(), self.username or 'Unknown person')


class LoginThrottle(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


@receiver(post_migrate, dispatch_uid='core.create_team_role_groups')
def create_team_role_groups(sender, app_config, using, apps, **kwargs):
    if app_config.label != 'core':
        return
    from .team_people import sync_team_roles

    sync_team_roles(using=using, app_config=app_config, apps=apps)
