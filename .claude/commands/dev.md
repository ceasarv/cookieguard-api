# Development Commands

## Run Server
```bash
python manage.py runserver
```

## Database
```bash
# Make migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

## Celery (for async tasks)
```bash
# Start worker
celery -A cookieguard worker -l info

# Start beat scheduler (for scheduled tasks)
celery -A cookieguard beat -l info
```

## Testing
```bash
python manage.py test
```

## Static Files
```bash
python manage.py collectstatic
```

## Shell
```bash
python manage.py shell
```

## Check for Issues
```bash
python manage.py check
```
