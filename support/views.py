from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
import os, resend


class HelpRequestView(APIView):
	authentication_classes = []  # 🔥 no auth required
	permission_classes = []  # 🔥 no auth required

	@extend_schema(
		request={"application/json": {"type": "object", "properties": {
			"name": {"type": "string"},
			"email": {"type": "string"},
			"subject": {"type": "string"},
			"message": {"type": "string"}
		}, "required": ["message"]}},
		responses={200: {"type": "object", "properties": {"success": {"type": "boolean"}}}},
		description="Submit a help request (public)",
		tags=["Support"]
	)
	def post(self, request):
		name = request.data.get("name", "Anonymous")
		email = request.data.get("email", "no-email-provided")
		subject = request.data.get("subject", "Support Request")
		message = request.data.get("message")

		if not message:
			return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

		try:
			sender_email = "support@resend.dev"
			receiver_email = os.environ.get("EMAIL_RECEIVER")
			resend.api_key = os.environ.get("RESEND_API_KEY")

			# 👇 Include name + email in subject for easy identification
			email_subject = f"Help request from {name} <{email}>"
			body = f"""
				<p><strong>From: </strong> {name} ({email})</p>
				<p><strong>Message: </strong>{message}</p>
			"""

			response = resend.Emails.send({
				"from": sender_email,
				"to": receiver_email,
				"subject": email_subject,
				"html": body,
			})

			print("[Help Request Email] ✅ Sent", response)
			return Response({"success": True}, status=status.HTTP_200_OK)

		except Exception as e:
			print("[Help Request Email Error]", e)
			return Response({"error": "Failed to send email"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
