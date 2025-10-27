import uuid
from django.db import models
from django.utils import timezone
from banners.models import Banner
from domains.models import Domain


class ConsentLog(models.Model):
	CHOICES = [
		("accept", "Accept"),
		("reject", "Reject"),
		("prefs", "Preferences"),
	]

	consent_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

	banner = models.ForeignKey(Banner, on_delete=models.CASCADE, related_name="consent_logs")
	domain = models.ForeignKey(Domain, on_delete=models.CASCADE)
	banner_version = models.PositiveIntegerField()  # snapshot of banner at time of consent

	choice = models.CharField(max_length=20, choices=CHOICES)
	categories = models.JSONField(default=dict)  # e.g., {"analytics": True, "ads": False}

	# GDPR-safe context
	truncated_ip = models.GenericIPAddressField(null=True, blank=True)
	user_agent = models.TextField(blank=True, null=True)

	created_at = models.DateTimeField(default=timezone.now)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"Consent {self.choice} on {self.domain.url} ({self.created_at.date()})"
