from rest_framework import serializers
from .models import Domain, CookieCategory
import re

URL_RE = re.compile(r"^(https?://)?([a-z0-9-]+\.)+[a-z]{2,}(:\d+)?(/.*)?$", re.I)


class DomainSerializer(serializers.ModelSerializer):
	class Meta:
		model = Domain
		fields = ["id", "url", "embed_key", "created_at", "updated_at", "last_scan_at"]
		read_only_fields = ["id", "embed_key", "created_at", "updated_at", "last_scan_at"]

	def validate_url(self, v: str) -> str:
		v = (v or "").strip()
		if not URL_RE.match(v):
			raise serializers.ValidationError("Enter a valid URL like https://example.com")
		if v.endswith("/") and v.count("/") > 2:
			v = v.rstrip("/")
		return v

	def create(self, validated):
		req = self.context.get("request")
		if hasattr(req.user, "account"):
			validated["account"] = req.user.account
		return super().create(validated)


class CookieCategorySerializer(serializers.ModelSerializer):
	class Meta:
		model = CookieCategory
		fields = ["id", "domain", "category", "script_name", "script_pattern", "description", "created_at"]
		read_only_fields = ["id", "created_at"]
