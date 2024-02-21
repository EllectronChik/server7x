import os
import json
from django.core.management.base import BaseCommand
from main.models import Region

class Command(BaseCommand):
    # Help text for the management command
    help = 'Load regions data into Region model'

    def handle(self, *args, **options):
        # Path to the JSON file containing region data
        json_file_path = os.path.join(os.path.dirname(__file__), 'data/region_data.json')

        # Check if the JSON file exists
        if not os.path.exists(json_file_path):
            # Display error message if the file doesn't exist
            self.stdout.write(self.style.ERROR("JSON file not found. Please make sure 'region_data.json' exists in the same directory."))
            return

        # Open the JSON file and load data
        with open(json_file_path, 'r') as json_file:
            region_data = json.load(json_file)

        # Loop through each region data entry
        for region in region_data:
            # Get or create a Region instance based on the name
            region_instance, created = Region.objects.get_or_create(
                name=region['name'],  # Name of the region
                defaults={
                    'flag_url': region['flag_url']  # Default flag URL for the region
                }
            )

            # Display success message based on whether the region was created or already exists
            if created:
                self.stdout.write(self.style.SUCCESS(f"Region '{region_instance.name}' created successfully."))
            else:
                self.stdout.write(self.style.SUCCESS(f"Region '{region_instance.name}' already exists."))
