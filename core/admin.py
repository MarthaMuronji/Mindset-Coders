from django.contrib import admin
from .models import Post, ContactMessage


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
