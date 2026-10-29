from django.contrib import admin
from django.utils import timezone
from .models import Post, ContactMessage, Registration, Story


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'published', 'created_at')
    list_filter = ('published',)
    search_fields = ('title', 'excerpt', 'content')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at', 'handled')
    list_filter = ('handled',)
    search_fields = ('name', 'email', 'message')
    # Messages arrive from the form, so nothing but the handled flag is editable
    readonly_fields = ('name', 'email', 'role', 'message', 'created_at')


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('learner_name', 'parent_name', 'parent_email', 'programme', 'created_at', 'handled')
    list_filter = ('handled', 'programme')
    search_fields = ('parent_name', 'learner_name', 'parent_email')
    # Registrations arrive from the form, so nothing but the handled flag is editable
    readonly_fields = (
        'parent_name', 'parent_email', 'parent_phone', 'learner_name',
        'learner_age', 'school_name', 'programme', 'consent', 'created_at',
    )


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    # name and email stay off the list, but the team can open a story to reply
    list_display = ('created_at', 'name', 'category', 'role', 'approved')
    list_filter = ('approved', 'category')
    search_fields = ('name', 'story')
    # The review area owns the review marks, so the admin only shows them
    readonly_fields = ('rejected', 'reviewed_at', 'reviewed_by')
    actions = ('approve_selected', 'unapprove_selected')

    @admin.action(description='Approve selected')
    def approve_selected(self, request, queryset):
        count = queryset.update(
            approved=True,
            rejected=False,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, 'Approved {} selected {}.'.format(count, 'story' if count == 1 else 'stories'))

    @admin.action(description='Unapprove selected')
    def unapprove_selected(self, request, queryset):
        # Back to waiting, with the review marks cleared
        count = queryset.update(
            approved=False,
            rejected=False,
            reviewed_at=None,
            reviewed_by=None,
        )
        self.message_user(request, 'Unapproved {} selected {}.'.format(count, 'story' if count == 1 else 'stories'))
