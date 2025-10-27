from django.contrib import admin
from .models import Banner


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
	list_display = ("id", "get_domains", "name", "position", "theme", "updated_at")
	search_fields = ("name", "domains__url")  # ✅ use the M2M lookup
	list_filter = ("position", "theme")

	def get_domains(self, obj):
		# Show comma-separated domain names (or URLs if that’s your Domain model’s field)
		return ", ".join([d.url for d in obj.domains.all()])

	get_domains.short_description = "Domains"
