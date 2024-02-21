from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Starts database'

    def handle(self, *args, **options):
        # Displaying a success message indicating the start of the database process.
        self.stdout.write(self.style.SUCCESS('Starting database...'))

        # Performing database migration.
        self.stdout.write(self.style.SUCCESS('Migrating database...'))
        call_command('migrate')

        # Loading leagues into the database.
        self.stdout.write(self.style.SUCCESS('Loading leagues...'))
        call_command('load_leagues')

        # Loading races into the database.
        self.stdout.write(self.style.SUCCESS('Loading races...'))
        call_command('load_races')

        # Loading regions into the database.
        self.stdout.write(self.style.SUCCESS('Loading regions...'))
        call_command('load_regions')

        # Loading league frames into the database.
        self.stdout.write(self.style.SUCCESS('Loading league frames...'))
        call_command('load_league_frames')
        
        # Displaying a success message indicating the successful completion of the database start process.
        self.stdout.write(self.style.SUCCESS('Database started successfully.'))
