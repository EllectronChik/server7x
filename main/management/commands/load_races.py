import os
import json
from django.core.management.base import BaseCommand
from main.models import Race


class Command(BaseCommand):
    help = 'Load races from JSON file'

    def handle(self, *args, **options):
        json_file_path = os.path.join(os.path.dirname(__file__), 'data/race_data.json')

        if not os.path.exists(json_file_path):
            self.stdout.write(self.style.ERROR("JSON file not found. Please make sure 'race_data.json' exists in the `data` directory."))
            return

        with open(json_file_path, 'r') as json_file:
            race_data = json.load(json_file)

        for race in race_data:
            race_instance, created = Race.objects.get_or_create(
                name=race['name'],
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Race '{race_instance.name}' created successfully."))
            else:
                self.stdout.write(self.style.SUCCESS(f"Race '{race_instance.name}' already exists."))