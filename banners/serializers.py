from rest_framework import serializers
from .models import Banner
from domains.models import Domain


class BannerSerializer(serializers.ModelSerializer):
	# For convenience: show the domain URLs
	domain_urls = serializers.SerializerMethodField(read_only=True)

	class Meta:
		model = Banner
		fields = [
			"id",
			"domains",  # M2M field (list of domain IDs)
			"domain_urls",  # Read-only helper
			"name",

			# Overlay
			"overlay_enabled",
			"overlay_color",
			"overlay_opacity",
			"overlay_blur_px",

			# Layout type & position
			"type",
			"position",

			# Toggles
			"has_reject_button",
			"show_preferences_button",
			"show_cookieguard_logo",  # ✅ NEW

			# Copy
			"title",
			"description",
			"accept_text",
			"reject_text",
			"prefs_text",

			# Theme / background
			"theme",
			"background_color",
			"background_opacity",

			# Button colors
			"accept_text_color",
			"accept_bg_color",
			"reject_text_color",
			"reject_bg_color",
			"prefs_text_color",
			"prefs_bg_color",

			# ✅ Button border settings
			"accept_border_color",
			"accept_border_width_px",
			"accept_border_radius_px",

			"reject_border_color",
			"reject_border_width_px",
			"reject_border_radius_px",

			"prefs_border_color",
			"prefs_border_width_px",
			"prefs_border_radius_px",

			# Dimensional/layout
			"width",
			"height",
			"padding_x_px",
			"padding_y_px",
			"spacing_px",
			"text_align",
			"z_index",

			# Border / shadow
			"border_radius_px",
			"border_color",
			"border_width_px",
			"shadow",
			"shadow_custom",

			# Versioning / meta
			"version",
			"created_at",
			"updated_at",
		]
		extra_kwargs = {
			"name": {"required": False, "allow_blank": True}
		}
		read_only_fields = ["version", "created_at", "updated_at"]

	def get_domain_urls(self, obj):
		return [d.url for d in obj.domains.all()]
