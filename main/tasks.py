from server7x.celery import app
from .models import LeagueFrame
from .utils import get_blizzard_league_data
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

log_file = 'task.log'
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

@app.task
def monthly_task():
    print('monthly task')
    try:
        logger.info('monthly task started')
        regions = ['eu', 'us', 'kr']

        for region in regions:
            logger.info(f'region: {region}')
            for league in range(1, 6):
                logger.info(f'league: {league}')
                max_rating = get_blizzard_league_data(region, league)
                logger.info(f'max rating: {max_rating}')
                obj = LeagueFrame.objects.filter(region=region, league=league).first()
                logger.info(f'obj: {obj}')
                if obj:
                    obj.frame_max = max_rating
                    obj.save()
                    logger.info('saved')
        logger.info('monthly task finished')
    except Exception as e:
        logger.error(e)