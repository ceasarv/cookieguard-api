web: gunicorn cookieguard.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2
worker: celery -A cookieguard worker --loglevel=info --concurrency=1 --max-tasks-per-child=1
beat: celery -A cookieguard beat --loglevel=info
