from django.contrib import admin
from .models import ConsentLog


@admin.register(ConsentLog)
class ConsentLogAdmin(admin.ModelAdmin):
	list_display = ("id", "domain", "choice", "created_at", "truncated_ip")
	search_fields = ("domain__url", "truncated_ip", "user_agent")
	list_filter = ("choice", "created_at")
	readonly_fields = ("created_at",)
