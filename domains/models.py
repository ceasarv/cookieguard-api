# domains/models.py
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Domain(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	url = models.URLField(max_length=500, unique=False)
	embed_key = models.CharField(max_length=40, unique=True, default="", blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	last_scan_at = models.DateTimeField(null=True, blank=True)
	user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
	is_ready = models.BooleanField(default=False)
	industry = models.CharField(max_length=120, null=True, blank=True)
	created_by = models.ForeignKey(
		User, null=True, blank=True, on_delete=models.SET_NULL, related_name="domains_created"
	)

	def save(self, *args, **kwargs):
		if not self.embed_key:
			import secrets
			self.embed_key = secrets.token_urlsafe(24)[:40]
		return super().save(*args, **kwargs)


class CookieCategory(models.Model):
	"""Defines which scripts/cookies belong to which consent category"""
	CATEGORY_CHOICES = [
		('necessary', 'Strictly Necessary'),
		('preferences', 'Preferences'),
		('analytics', 'Analytics'),
		('marketing', 'Marketing'),
	]

	domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='cookie_categories')
	category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
	script_name = models.CharField(max_length=200, help_text="e.g., Google Analytics, Facebook Pixel")
	script_pattern = models.TextField(help_text="URL pattern or selector to block (e.g., 'googletagmanager.com/gtag')")
	description = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ['domain', 'script_name']
		verbose_name_plural = "Cookie categories"

	def __str__(self):
		return f"{self.script_name} ({self.category}) - {self.domain.url}"
