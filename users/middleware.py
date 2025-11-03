from django.http import JsonResponse


class BlockedUserMiddleware:
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		user = getattr(request, "user", None)
		if user and user.is_authenticated and getattr(user, "is_blocked", False):
			return JsonResponse(
				{"detail": "Your account has been suspended. Please contact support."},
				status=403,
			)
		return self.get_response(request)
