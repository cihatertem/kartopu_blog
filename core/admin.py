from django.contrib import admin

# Register your models here.
from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_spam", "created_at")
    list_filter = ("is_spam", "created_at")
    search_fields = ("name", "email", "subject", "message")
