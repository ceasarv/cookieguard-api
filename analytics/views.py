from django.db.models import Count, Q
from django.db.models.functions import TruncDate

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from consents.models import ConsentLog


class ConsentAnalyticsView(APIView):
	"""
	Returns daily consent stats for the logged-in user's domains/banners.

	Example:
	GET /api/analytics/consents/
	GET /api/analytics/consents/?domain_id=123
	GET /api/analytics/consents/?banner_id=5
	"""

	permission_classes = [IsAuthenticated]

	@extend_schema(
		parameters=[
			OpenApiParameter(name='domain_id', type=str, location=OpenApiParameter.QUERY, required=False),
			OpenApiParameter(name='banner_id', type=str, location=OpenApiParameter.QUERY, required=False),
		],
		responses={200: {"type": "array", "items": {"type": "object", "properties": {
			"date": {"type": "string", "format": "date"},
			"total": {"type": "integer"},
			"accepts": {"type": "integer"},
			"rejects": {"type": "integer"},
			"prefs": {"type": "integer"},
			"accept_rate": {"type": "number", "nullable": True},
			"reject_rate": {"type": "number", "nullable": True}
		}}}},
		description="Get daily consent analytics for the authenticated user's domains",
		tags=["Analytics"]
	)
	def get(self, request):
		user = request.user

		domain_id = request.query_params.get("domain_id")
		banner_id = request.query_params.get("banner_id")

		qs = ConsentLog.objects.filter(domain__user=user)

		if domain_id:
			qs = qs.filter(domain_id=domain_id)
		if banner_id:
			qs = qs.filter(banner_id=banner_id)

		data = (
			qs.annotate(date=TruncDate("created_at"))
			.values("date")
			.annotate(
				total=Count("id"),
				accepts=Count("id", filter=Q(choice="accept")),
				rejects=Count("id", filter=Q(choice="reject")),
				prefs=Count("id", filter=Q(choice="prefs")),
			)
			.order_by("-date")  # 🔥 newest first
		)

		result = []
		for row in data:
			total = row["total"]
			accepts = row["accepts"]
			rejects = row["rejects"]
			prefs = row["prefs"]

			result.append({
				"date": row["date"],
				"total": total,
				"accepts": accepts,
				"rejects": rejects,
				"prefs": prefs,
				"accept_rate": accepts / total if total else None,
				"reject_rate": rejects / total if total else None,
			})

		return Response(result)
