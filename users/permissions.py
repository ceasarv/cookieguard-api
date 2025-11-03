from rest_framework.permissions import BasePermission


class NotBlocked(BasePermission):
	"""
	Deny all requests for blocked users.
	"""
	message = "Your account has been suspended. Please contact support."

	def has_permission(self, request, view):
		user = request.user
		if user and user.is_authenticated and getattr(user, "is_blocked", False):
			return False
		return True
