import os
import json
from django.core.management.base import BaseCommand
from main.models import LeagueFrame, League


class Command(BaseCommand):
    help = 'Loads league frames'

    def handle(self, *args, **options):
        json_file_path = os.path.join(os.path.dirname(__file__), 'data/league_frames_data.json')

        if not os.path.exists(json_file_path):
            self.stdout.write(self.style.ERROR("JSON file not found. Please make sure 'league_frames_data.json' exists in the `data` directory."))
            return

        with open(json_file_path, 'r') as json_file:
            league_frames_data = json.load(json_file)

        for league_frame in league_frames_data:
            region = league_frame['region']
            league = League.objects.get(id=league_frame['league'])
            frame_max = league_frame['frame_max']
            league_frame_instance, created = LeagueFrame.objects.get_or_create(
                region=region,
                league=league,
                defaults={
                    'frame_max': frame_max
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"League frame '{league_frame_instance}' created successfully."))
            else:
                self.stdout.write(self.style.SUCCESS(f"League frame '{league_frame_instance}' already exists."))