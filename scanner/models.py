from django.db import models


class ScanResult(models.Model):
	url = models.URLField()
	has_consent_banner = models.BooleanField(default=False)
	compliance_score = models.IntegerField()
	first_party_count = models.PositiveIntegerField()
	third_party_count = models.PositiveIntegerField()
	tracker_count = models.PositiveIntegerField()
	unclassified_count = models.PositiveIntegerField()
	issues = models.JSONField(default=list)  # store issue strings like a list
	duration = models.FloatField(help_text="Duration in seconds")
	scanned_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Scan for {self.url} at {self.scanned_at.strftime('%Y-%m-%d %H:%M')}"


class Cookie(models.Model):
	scan = models.ForeignKey(ScanResult, on_delete=models.CASCADE, related_name="cookies")
	name = models.CharField(max_length=255)
	domain = models.CharField(max_length=255)
	path = models.CharField(max_length=255)
	expires = models.CharField(max_length=255)  # Session or timestamp string
	type = models.CharField(max_length=20, choices=[('First-party', 'First-party'), ('Third-party', 'Third-party')])
	classification = models.CharField(max_length=50, default='Unclassified')

	def __str__(self):
		return f"{self.name} ({self.type})"
