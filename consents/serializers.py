from rest_framework import serializers
from .models import ConsentLog


class ConsentLogSerializer(serializers.ModelSerializer):
	class Meta:
		model = ConsentLog
		fields = [
			"consent_id",
			"banner",
			"domain",
			"banner_version",
			"choice",
			"categories",
			"truncated_ip",
			"user_agent",
			"created_at",
		]
		read_only_fields = ["consent_id", "created_at", "banner_version"]

	def create(self, validated_data):
		# Pull banner version automatically
		banner = validated_data["banner"]
		validated_data["banner_version"] = banner.version
		return super().create(validated_data)
