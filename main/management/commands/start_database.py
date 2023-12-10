from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Starts database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting database...'))

        self.stdout.write(self.style.SUCCESS('Migrating database...'))
        call_command('migrate')

        self.stdout.write(self.style.SUCCESS('Loading leagues...'))
        call_command('load_leagues')

        self.stdout.write(self.style.SUCCESS('Loading races...'))
        call_command('load_races')

        self.stdout.write(self.style.SUCCESS('Loading regions...'))
        call_command('load_regions')

        self.stdout.write(self.style.SUCCESS('Loading league frames...'))
        call_command('load_league_frames')
        
        self.stdout.write(self.style.SUCCESS('Database started successfully.'))