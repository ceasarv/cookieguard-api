from django.contrib import admin
from .models import SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
	list_display = ("id", "name", "email", "subject", "status", "created_at")
	search_fields = ("name", "email", "subject", "message")
	list_filter = ("status", "created_at")
	readonly_fields = ("created_at",)
