import os
import json
from django.core.management.base import BaseCommand
from main.models import League

class Command(BaseCommand):
    # Help message for the command
    help = 'Load leagues from JSON file'

    def handle(self, *args, **options):
        # Path to the JSON file
        json_file_path = os.path.join(os.path.dirname(__file__), 'data/league_data.json')

        # Check if the JSON file exists
        if not os.path.exists(json_file_path):
            # Display an error message if the file doesn't exist
            self.stdout.write(self.style.ERROR("JSON file not found. Please make sure 'league_data.json' exists in the `data` directory."))
            return

        # Open and load data from the JSON file
        with open(json_file_path, 'r') as json_file:
            league_data = json.load(json_file)

        # Loop through the league data
        for league in league_data:
            # Get or create a League instance based on the data from JSON
            league_instance, created = League.objects.get_or_create(
                name=league['name'],
            )

            # Check if the League instance was newly created or already existed
            if created:
                # Display a success message if the League instance was created
                self.stdout.write(self.style.SUCCESS(f"League '{league_instance.name}' created successfully."))
            else:
                # Display a success message if the League instance already existed
                self.stdout.write(self.style.SUCCESS(f"League '{league_instance.name}' already exists."))
