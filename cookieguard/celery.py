import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cookieguard.settings')  # adjust if needed

app = Celery('cookieguard')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
