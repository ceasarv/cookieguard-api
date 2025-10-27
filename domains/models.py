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
