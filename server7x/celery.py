import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server7x.settings')

app = Celery('server7x')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'every': {
        'task': 'main.tasks.monthly_task',
        'schedule': crontab(),
    }
}