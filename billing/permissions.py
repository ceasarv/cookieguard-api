from rest_framework.permissions import BasePermission
from .guards import has_billing_access


class HasPaidPlan(BasePermission):
	message = "Your subscription is not active."

	def has_permission(self, request, view):
		return has_billing_access(request.user)
