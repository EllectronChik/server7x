import os
import json
from django.core.management.base import BaseCommand
from main.models import Region

class Command(BaseCommand):
    help = 'Load regions data into Region model'

    def handle(self, *args, **options):
        json_file_path = os.path.join(os.path.dirname(__file__), 'data/region_data.json')

        if not os.path.exists(json_file_path):
            self.stdout.write(self.style.ERROR("JSON file not found. Please make sure 'region_data.json' exists in the same directory."))
            return

        with open(json_file_path, 'r') as json_file:
            region_data = json.load(json_file)

        for region in region_data:
            region_instance, created = Region.objects.get_or_create(
                name=region['name'],
                defaults={
                    'flag_url': region['flag_url']
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Region '{region_instance.name}' created successfully."))
            else:
                self.stdout.write(self.style.SUCCESS(f"Region '{region_instance.name}' already exists."))
