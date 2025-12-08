from django.db import models
from domains.models import Domain


class Banner(models.Model):
	domains = models.ManyToManyField(Domain, related_name="banners", blank=True)
	name = models.CharField(max_length=255, blank=True, default="")
	is_active = models.BooleanField(default=True)

	# ---------- Overlay settings ----------
	overlay_enabled = models.BooleanField(default=False)
	overlay_color = models.CharField(max_length=20, default="#000000")
	overlay_opacity = models.FloatField(default=0.5)
	overlay_blur_px = models.PositiveSmallIntegerField(default=0)

	# ---------- Layout type ----------
	TYPE_CHOICES = [
		("bar", "Bar"),
		("modal", "Modal"),
		("panel", "Panel"),
	]

	type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="bar")

	# ---------- Position ----------
	POSITION_CHOICES = [
		("top", "Top"),
		("bottom", "Bottom"),
		("top-left", "Top Left"),
		("top-right", "Top Right"),
		("bottom-left", "Bottom Left"),
		("bottom-right", "Bottom Right"),
		("center", "Center"),
	]
	position = models.CharField(max_length=20, choices=POSITION_CHOICES, default="bottom")

	# ---------- Compliance toggles ----------
	has_reject_button = models.BooleanField(default=True)
	show_preferences_button = models.BooleanField(default=True)
	show_cookieguard_logo = models.BooleanField(default=True)

	# ---------- Copy ----------
	title = models.CharField(max_length=255, default="We use cookies 🍪")
	description = models.TextField(default="We use cookies to improve your experience…")
	accept_text = models.CharField(max_length=50, default="Accept all")
	reject_text = models.CharField(max_length=50, default="Reject")
	prefs_text = models.CharField(max_length=50, default="Preferences")
	cookie_policy_text = models.TextField(blank=True, default="")
	text_color = models.CharField(max_length=20, default="#111827")  # dark gray

	# ---------- Theme / brand ----------
	theme = models.CharField(
		max_length=20,
		choices=[("light", "Light"), ("dark", "Dark")],
		default="light",
	)
	background_color = models.CharField(max_length=20, default="#ffffff")
	background_opacity = models.FloatField(default=1.0)

	# ---------- Button colors ----------
	accept_text_color = models.CharField(max_length=20, default="#ffffff")
	accept_bg_color = models.CharField(max_length=20, default="#2563eb")

	reject_text_color = models.CharField(max_length=20, default="#111827")
	reject_bg_color = models.CharField(max_length=20, default="#ffffff")

	prefs_text_color = models.CharField(max_length=20, default="#111827")
	prefs_bg_color = models.CharField(max_length=20, default="#ffffff")

	# ---------- New: per-button borders ----------
	accept_border_color = models.CharField(max_length=20, default="#E5E7EB")
	accept_border_width_px = models.PositiveSmallIntegerField(default=1)
	accept_border_radius_px = models.PositiveSmallIntegerField(default=8)

	reject_border_color = models.CharField(max_length=20, default="#E5E7EB")
	reject_border_width_px = models.PositiveSmallIntegerField(default=1)
	reject_border_radius_px = models.PositiveSmallIntegerField(default=8)

	prefs_border_color = models.CharField(max_length=20, default="#E5E7EB")
	prefs_border_width_px = models.PositiveSmallIntegerField(default=1)
	prefs_border_radius_px = models.PositiveSmallIntegerField(default=8)

	# ---------- Dimensional / layout styling ----------
	width = models.CharField(max_length=20, blank=True, null=True)
	height = models.CharField(max_length=20, blank=True, null=True)

	padding_x_px = models.PositiveSmallIntegerField(default=16)
	padding_y_px = models.PositiveSmallIntegerField(default=12)
	spacing_px = models.PositiveSmallIntegerField(default=12)

	text_align = models.CharField(
		max_length=10,
		choices=[("left", "Left"), ("center", "Center"), ("right", "Right")],
		default="left",
	)
	z_index = models.IntegerField(default=10)

	# ---------- Border / radius / shadow ----------
	border_radius_px = models.PositiveSmallIntegerField(default=8)
	border_color = models.CharField(max_length=20, default="#E5E7EB")
	border_width_px = models.PositiveSmallIntegerField(default=1)

	SHADOW_CHOICES = [
		("none", "None"),
		("sm", "Small"),
		("md", "Medium"),
		("lg", "Large"),
		("xl", "Extra Large"),
		("custom", "Custom"),
	]
	shadow = models.CharField(max_length=10, choices=SHADOW_CHOICES, default="md")
	shadow_custom = models.CharField(max_length=200, blank=True, null=True)

	# ---------- Versioning ----------
	version = models.PositiveIntegerField(default=1)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	VERSIONED_FIELDS = [
		"title", "accept_text", "reject_text", "prefs_text",
		"type", "position",
		"overlay_enabled", "overlay_color", "overlay_opacity", "overlay_blur_px",
		"theme", "background_color", "background_opacity",
		"width", "height",
		"padding_x_px", "padding_y_px", "spacing_px", "text_align", "z_index",
		"border_radius_px", "border_color", "border_width_px",
		"shadow", "shadow_custom",
	]

	def save(self, *args, **kwargs):
		"""Auto-bump version when any versioned field changes."""
		if self.pk:
			old = Banner.objects.filter(pk=self.pk).first()
			if old:
				for f in self.VERSIONED_FIELDS:
					if getattr(old, f) != getattr(self, f):
						self.version = old.version + 1
						break
		super().save(*args, **kwargs)

	def __str__(self):
		domains = ", ".join(d.url for d in self.domains.all()[:2])
		if self.domains.count() > 2:
			domains += "…"
		return f"Banner v{self.version} ({domains or 'no domains'})"

	# ---------- Helpers for FE ----------
	@property
	def box_shadow_css(self) -> str:
		if self.shadow == "custom" and self.shadow_custom:
			return self.shadow_custom
		presets = {
			"none": "none",
			"sm": "0 1px 2px rgba(0,0,0,0.05)",
			"md": "0 4px 6px rgba(0,0,0,0.10)",
			"lg": "0 10px 15px rgba(0,0,0,0.15)",
			"xl": "0 20px 25px rgba(0,0,0,0.20)",
		}
		return presets.get(self.shadow, presets["md"])

	def style_dict(self) -> dict:
		"""Convenience map the FE can consume directly."""
		return {
			"width": self.width or None,
			"height": self.height or None,
			"backgroundColor": self.background_color,
			"backgroundOpacity": self.background_opacity,
			"paddingX": f"{self.padding_x_px}px",
			"paddingY": f"{self.padding_y_px}px",
			"gap": f"{self.spacing_px}px",
			"textAlign": self.text_align,
			"zIndex": self.z_index,
			"borderRadius": f"{self.border_radius_px}px",
			"borderColor": self.border_color,
			"borderWidth": f"{self.border_width_px}px",
			"boxShadow": self.box_shadow_css,
		}
