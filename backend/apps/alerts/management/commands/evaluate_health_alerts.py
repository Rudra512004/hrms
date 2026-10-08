from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.alerts.services import AlertEvaluationService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Evaluates all enabled work health alerts and dispatches notifications.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Optional target date in YYYY-MM-DD format. Defaults to today.',
        )

    def handle(self, *args, **options):
        target_date_str = options.get('date')
        if target_date_str:
            target_date = timezone.datetime.strptime(target_date_str, "%Y-%m-%d").date()
        else:
            target_date = timezone.now().date()

        self.stdout.write(self.style.SUCCESS(f'Starting alert evaluation for date: {target_date}'))
        
        try:
            AlertEvaluationService.evaluate_all(target_date=target_date)
            self.stdout.write(self.style.SUCCESS('Successfully evaluated health alerts.'))
        except Exception as e:
            logger.exception("Failed to evaluate health alerts.")
            self.stderr.write(self.style.ERROR(f'Error during evaluation: {e}'))
