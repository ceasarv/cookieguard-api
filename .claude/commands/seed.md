# Seed & Test Data Commands

## Seed Test Users

Create test users with domains, banners, consents, and usage data:

```bash
python manage.py seed_test_data
```

### Options

- `--users N` - Number of test users (default: 3)
- `--consents N` - Consents per user (default: 100)
- `--clear` - Remove existing test data first

### Examples

```bash
# Default: 3 users with 100 consents each
python manage.py seed_test_data

# 5 users with 500 consents each
python manage.py seed_test_data --users 5 --consents 500

# Clear existing test data and recreate
python manage.py seed_test_data --clear
```

### Test Login
- Email: `testuser1@test.cookieguard.app` (or testuser2, testuser3, etc.)
- Password: `testpass123`

### What Gets Created
- Test users with billing profiles
- Domains (from test domain list)
- Banners linked to domains
- Usage records with random pageviews
- Consent logs spread over last 30 days (65% accept, 25% reject, 10% prefs)

---

## Set Usage for Existing User

Set pageview usage for any user (useful for testing usage limits UI):

```bash
python manage.py set_usage --email user@example.com --pageviews 7500
```

### Options

- `--email EMAIL` - User email (required, or use --user-id)
- `--user-id UUID` - User UUID (required, or use --email)
- `--pageviews N` - Exact pageview count (required, or use --percent)
- `--percent N` - Percentage of plan limit, e.g. 75 for 75% (required, or use --pageviews)
- `--scans N` - Scans used (optional)
- `--reset-warnings` - Reset all warning flags (70%, 80%, 100%, hard limit)
- `--send-warning` - Trigger appropriate warning email based on usage level

### Examples

```bash
# Set exact pageview count
python manage.py set_usage --email user@example.com --pageviews 7500

# Set by user UUID
python manage.py set_usage --user-id ed66fcbd-f26e-4952-b848-1d7cba0eab7b --pageviews 200

# Set to 75% of their plan limit
python manage.py set_usage --email user@example.com --percent 75

# Set to 95% (near limit - shows warning state)
python manage.py set_usage --email user@example.com --percent 95

# Set to 110% (over limit)
python manage.py set_usage --email user@example.com --percent 110

# Test warning emails: set to 70% and send the email
python manage.py set_usage --email user@example.com --percent 70 --reset-warnings --send-warning

# Test 80% warning
python manage.py set_usage --email user@example.com --percent 80 --reset-warnings --send-warning
```

### Warning Email Thresholds

| Threshold | Type | Plans |
|-----------|------|-------|
| 70% | `early_warning` | Free only |
| 80% | `approaching` | All |
| 100% | `reached` | All |
| 115% | `blocked` | All |

---

## Other Seed Commands

```bash
# Seed known cookies database
python manage.py seed_cookies

# Seed consent logs (standalone)
python manage.py seed_consents
```
