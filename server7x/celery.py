import os
import datetime
from celery import Celery
from celery.schedules import crontab

run_hour = datetime.datetime.utcnow().hour
run_minute = datetime.datetime.utcnow().minute

if run_minute == 59:
    run_minute = 0
    if run_hour == 23:
        run_hour = 0
    else:
        run_hour = run_hour + 1
else:
    run_minute = run_minute + 1

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server7x.settings')

app = Celery('server7x')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'every': {
        'task': 'main.tasks.daily_task',
        'schedule': crontab(hour=run_hour, minute=run_minute),
    },
    'update_players_data': {
        'task': 'main.tasks.update_players_data',
        'schedule': crontab(hour=run_hour, minute=run_minute),
    },
}
app.conf.task_always_eager = False
app.conf.task_reject_on_worker_lost = True
app.conf.task_acks_late = True