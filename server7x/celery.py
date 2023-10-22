import os
import datetime
from celery import Celery
from celery.schedules import crontab

run_hour = datetime.datetime.utcnow().hour
run_minute = datetime.datetime.utcnow().minute

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server7x.settings')

app = Celery('server7x')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'every': {
        'task': 'main.tasks.monthly_task',
        'schedule': crontab(hour=run_hour, minute=run_minute),
    }
}
app.conf.task_always_eager = False
app.conf.task_reject_on_worker_lost = True
app.conf.task_acks_late = True