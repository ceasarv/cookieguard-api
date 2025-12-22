import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cookieguard.settings')  # adjust if needed

app = Celery('cookieguard')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat schedule for automated tasks
app.conf.beat_schedule = {
	# Daily auto-scans for Agency plan users (runs at 3 AM UTC)
	'daily-agency-scans': {
		'task': 'scanner.tasks.run_scheduled_scans',
		'schedule': crontab(hour=3, minute=0),
		'args': ('daily',),
	},
	# Weekly auto-scans for Pro plan users (runs Monday at 4 AM UTC)
	'weekly-pro-scans': {
		'task': 'scanner.tasks.run_scheduled_scans',
		'schedule': crontab(hour=4, minute=0, day_of_week=1),
		'args': ('weekly',),
	},
	# Monthly email reports for Pro+ users (1st of month at 9 AM UTC)
	'monthly-email-reports': {
		'task': 'billing.tasks.send_monthly_reports',
		'schedule': crontab(hour=9, minute=0, day_of_month=1),
	},
}
