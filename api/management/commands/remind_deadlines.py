# api/management/commands/remind_deadlines.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from api.models import Task  # popraw, jeśli Twój Task jest w `tasks.models`
from datetime import timedelta

class Command(BaseCommand):
    help = 'Wysyła przypomnienia mailowe 3 dni przed deadlinem'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        reminder_date = today + timedelta(days=3)

        tasks = Task.objects.filter(deadline__date=reminder_date)

        for task in tasks:
            recipient = task.assigned_to
            if recipient and recipient.email:
                send_mail(
                    subject=f'Przypomnienie: termin zadania "{task.title}"',
                    message=(
                        f'Cześć {recipient.username},\n\n'
                        f'Przypominamy, że zadanie "{task.title}" ma termin za 3 dni: {task.deadline}.\n'
                        f'Sprawdź w TickTask!'
                    ),
                    from_email=None,
                    recipient_list=[recipient.email],
                )

        self.stdout.write(self.style.SUCCESS(f'Przypomnienia wysłane dla {tasks.count()} zadań.'))
