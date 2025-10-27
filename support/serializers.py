from rest_framework import serializers
from .models import SupportTicket


class SupportTicketSerializer(serializers.ModelSerializer):
	class Meta:
		model = SupportTicket
		fields = ["id", "email", "subject", "message", "status", "created_at"]
		read_only_fields = ["id", "status", "created_at"]
