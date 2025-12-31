# Seed Test Data

Run the seed command to create test users with domains, banners, consents, and usage data:

```bash
python manage.py seed_test_data
```

## Options

- `--users N` - Number of test users (default: 3)
- `--consents N` - Consents per user (default: 100)
- `--clear` - Remove existing test data first

## Examples

```bash
# Default: 3 users with 100 consents each
python manage.py seed_test_data

# 5 users with 500 consents each
python manage.py seed_test_data --users 5 --consents 500

# Clear existing test data and recreate
python manage.py seed_test_data --clear
```

## Test Login
- Email: `testuser1@test.cookieguard.app` (or testuser2, testuser3, etc.)
- Password: `testpass123`

## What Gets Created
- Test users with billing profiles
- Domains (from test domain list)
- Banners linked to domains
- Usage records with random pageviews
- Consent logs spread over last 30 days (65% accept, 25% reject, 10% prefs)
