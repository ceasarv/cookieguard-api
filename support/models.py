from django.db import models


class SupportTicket(models.Model):
	name = models.CharField(max_length=200, blank=True)  # 👈 added
	email = models.EmailField()
	subject = models.CharField(max_length=200)
	message = models.TextField()
	status = models.CharField(
		max_length=20,
		choices=[("open", "Open"), ("closed", "Closed")],
		default="open"
	)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Ticket #{self.id} - {self.subject}"
