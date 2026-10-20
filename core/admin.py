from django.contrib import admin
from .models import Post, ContactMessage, Story


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


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    # name and email stay off the list, but the team can open a story to reply
    list_display = ('created_at', 'name', 'category', 'role', 'approved')
    list_filter = ('approved', 'category')
    search_fields = ('name', 'story')
    actions = ('approve_selected', 'unapprove_selected')

    @admin.action(description='Approve selected')
    def approve_selected(self, request, queryset):
        count = queryset.update(approved=True)
        self.message_user(request, 'Approved {} selected {}.'.format(count, 'story' if count == 1 else 'stories'))

    @admin.action(description='Unapprove selected')
    def unapprove_selected(self, request, queryset):
        count = queryset.update(approved=False)
        self.message_user(request, 'Unapproved {} selected {}.'.format(count, 'story' if count == 1 else 'stories'))
