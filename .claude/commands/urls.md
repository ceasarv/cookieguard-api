# CookieGuard API URLs

## Development URLs
- **API Base**: http://localhost:8000/api/
- **Admin**: http://localhost:8000/admin/
- **Swagger Docs**: http://localhost:8000/api/docs/ (staff only)
- **ReDoc**: http://localhost:8000/api/redoc/ (staff only)
- **OpenAPI Schema**: http://localhost:8000/api/schema/

## API Endpoints

### Auth
- POST `/api/auth/register/` - Register new user
- POST `/api/auth/login/` - Login with email/password
- POST `/api/auth/google/` - Google OAuth login
- GET/PATCH `/api/auth/me/` - Current user profile
- GET `/api/auth/users/` - List all users (staff only)
- POST `/api/token/` - Get JWT token
- POST `/api/token/refresh/` - Refresh JWT token

### Billing
- GET `/api/billing/me/` - Current user billing
- GET `/api/billing/usage/` - Current month usage
- GET `/api/billing/public/plans/` - Public plan info
- POST `/api/billing/checkout-session/` - Create Stripe checkout
- POST `/api/billing/portal-session/` - Create billing portal

### Domains
- GET/POST `/api/domains/` - List/create domains
- GET/PATCH/DELETE `/api/domains/{id}/` - Domain detail

### Banners
- GET/POST `/api/banners/` - List/create banners
- GET/PATCH/DELETE `/api/banners/{id}/` - Banner detail

### Consents
- GET `/api/consents/` - List consent logs
- POST `/api/consents/log/` - Log consent (public)
- POST `/api/consents/pageview/` - Track pageview (public)
- GET `/api/consents/export/` - Export CSV (Pro+)

### Scanner
- POST `/api/scan/` - Public scan
- POST `/api/scan/trigger/` - Authenticated scan
- GET `/api/scan/status/{task_id}/` - Check scan status

### Analytics
- GET `/api/analytics/consents/` - Consent analytics
