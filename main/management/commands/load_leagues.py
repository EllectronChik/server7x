import os
import json
from django.core.management.base import BaseCommand
from main.models import League


class Command(BaseCommand):
    help = 'Load leagues from JSON file'

    def handle(self, *args, **options):
        json_file_path = os.path.join(os.path.dirname(__file__), 'data/league_data.json')

        if not os.path.exists(json_file_path):
            self.stdout.write(self.style.ERROR("JSON file not found. Please make sure 'league_data.json' exists in the `data` directory."))
            return

        with open(json_file_path, 'r') as json_file:
            league_data = json.load(json_file)

        for league in league_data:
            league_instance, created = League.objects.get_or_create(
                name=league['name'],
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"League '{league_instance.name}' created successfully."))
            else:
                self.stdout.write(self.style.SUCCESS(f"League '{league_instance.name}' already exists."))