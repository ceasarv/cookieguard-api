# billing/middleware.py
from .guards import has_billing_access


class BillingAccessMiddleware:
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		request.has_billing_access = has_billing_access(request.user)
		return self.get_response(request)
