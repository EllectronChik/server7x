import os
import json
from django.core.management.base import BaseCommand
from main.models import LeagueFrame, League


class Command(BaseCommand):
    help = 'Loads league frames'  # Description of what the command does

    def handle(self, *args, **options):
        # Define the path to the JSON file containing league frames data
        json_file_path = os.path.join(os.path.dirname(__file__), 'data/league_frames_data.json')

        # Check if the JSON file exists
        if not os.path.exists(json_file_path):
            # If the JSON file does not exist, display an error message and exit
            self.stdout.write(self.style.ERROR("JSON file not found. Please make sure 'league_frames_data.json' exists in the `data` directory."))
            return

        # Open the JSON file and load its contents into a variable
        with open(json_file_path, 'r') as json_file:
            league_frames_data = json.load(json_file)

        # Iterate over each league frame in the loaded data
        for league_frame in league_frames_data:
            # Extract relevant data for league frame creation
            region = league_frame['region']
            league = League.objects.get(id=league_frame['league'])
            frame_max = league_frame['frame_max']

            # Try to get the LeagueFrame instance from the database; if it doesn't exist, create it
            league_frame_instance, created = LeagueFrame.objects.get_or_create(
                region=region,
                league=league,
                defaults={
                    'frame_max': frame_max
                }
            )

            # Check if the LeagueFrame instance was created or already existed
            if created:
                # If the LeagueFrame instance was created, display a success message
                self.stdout.write(self.style.SUCCESS(f"League frame '{league_frame_instance}' created successfully."))
            else:
                # If the LeagueFrame instance already existed, display a message indicating that
                self.stdout.write(self.style.SUCCESS(f"League frame '{league_frame_instance}' already exists."))
