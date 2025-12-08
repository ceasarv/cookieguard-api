from django.contrib import admin
from django.db.models import Field
from .models import Domain, CookieCategory


def has_field(name: str) -> bool:
	return any(f.name == name for f in Domain._meta.get_fields() if isinstance(f, Field))


base_list = [f for f in ("url", "embed_key", "last_scan_at", "created_at") if has_field(f)]
base_filters = [f for f in ("last_scan_at", "is_active") if has_field(f)]


class CookieCategoryInline(admin.TabularInline):
	model = CookieCategory
	extra = 1
	fields = ("category", "script_name", "script_pattern", "description")


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
	list_display = tuple(base_list)
	list_filter = tuple(base_filters)
	search_fields = tuple([f for f in ("url", "embed_key") if has_field(f)])
	ordering = ("-created_at",)
	readonly_fields = tuple([f for f in ("embed_key", "created_at", "updated_at") if has_field(f)])
	inlines = [CookieCategoryInline]


@admin.register(CookieCategory)
class CookieCategoryAdmin(admin.ModelAdmin):
	list_display = ("script_name", "category", "domain", "created_at")
	list_filter = ("category", "created_at")
	search_fields = ("script_name", "script_pattern", "domain__url")
	ordering = ("-created_at",)
	readonly_fields = ("created_at",)
	autocomplete_fields = ("domain",)
