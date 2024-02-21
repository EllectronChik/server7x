import os
import json
from django.core.management.base import BaseCommand
from main.models import Race


class Command(BaseCommand):
    # Help text for the command
    help = 'Load races from JSON file'

    def handle(self, *args, **options):
        # Define the path to the JSON file
        json_file_path = os.path.join(os.path.dirname(__file__), 'data/race_data.json')

        # Check if the JSON file exists
        if not os.path.exists(json_file_path):
            # Inform the user if the JSON file is not found
            self.stdout.write(self.style.ERROR("JSON file not found. Please make sure 'race_data.json' exists in the `data` directory."))
            return

        # Open the JSON file and load its contents
        with open(json_file_path, 'r') as json_file:
            race_data = json.load(json_file)

        # Iterate over each race data entry
        for race in race_data:
            # Get or create a Race instance based on the name
            race_instance, created = Race.objects.get_or_create(
                name=race['name'],
            )

            # Inform the user about the status of the Race instance creation
            if created:
                self.stdout.write(self.style.SUCCESS(f"Race '{race_instance.name}' created successfully."))
            else:
                self.stdout.write(self.style.SUCCESS(f"Race '{race_instance.name}' already exists."))
