from rest_framework.permissions import BasePermission
from .guards import has_billing_access, get_user_plan, can_use_feature


class HasPaidPlan(BasePermission):
	"""Requires any active paid subscription (Pro or Agency)."""
	message = "Your subscription is not active."

	def has_permission(self, request, view):
		return has_billing_access(request.user)


class HasProPlan(BasePermission):
	"""Requires Pro plan or higher (Pro or Agency)."""
	message = "This feature requires a Pro or Agency plan."

	def has_permission(self, request, view):
		plan = get_user_plan(request.user)
		return plan in ("pro", "agency")


class HasAgencyPlan(BasePermission):
	"""Requires Agency plan."""
	message = "This feature requires an Agency plan."

	def has_permission(self, request, view):
		return get_user_plan(request.user) == "agency"


class CanRemoveBranding(BasePermission):
	"""Check if user can remove CookieGuard branding."""
	message = "Removing branding requires a Pro or Agency plan."

	def has_permission(self, request, view):
		return can_use_feature(request.user, "remove_branding")


class CanUseCookieCategorization(BasePermission):
	"""Check if user can use cookie categorization."""
	message = "Cookie categorization requires a Pro or Agency plan."

	def has_permission(self, request, view):
		return can_use_feature(request.user, "cookie_categorization")


class CanExportCSV(BasePermission):
	"""Check if user can export data to CSV."""
	message = "CSV export requires a Pro or Agency plan."

	def has_permission(self, request, view):
		return can_use_feature(request.user, "csv_export")


class CanViewAuditLogs(BasePermission):
	"""Check if user can view audit logs."""
	message = "Audit logs require an Agency plan."

	def has_permission(self, request, view):
		return can_use_feature(request.user, "audit_logs")


class CanManageTeam(BasePermission):
	"""Check if user can manage team members."""
	message = "Team management requires an Agency plan."

	def has_permission(self, request, view):
		return can_use_feature(request.user, "team_members")
