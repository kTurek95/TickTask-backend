from .models import Activity
from django.utils import timezone
from django.core.mail import send_mail
from .models import Task
from datetime import timedelta

def log_activity(user, action, source_user=None):
    Activity.objects.create(user=user, action=action, source_user=source_user)



def remind_deadlines():
    today = timezone.now().date()
    reminder_date = today + timedelta(days=2)  # <-- 2 dni przed!

    tasks = Task.objects.filter(deadline__date=reminder_date)

    print(f"🔔 Sprawdzam deadliny na {reminder_date} — znaleziono {tasks.count()} zadań")

    for task in tasks:
        recipient = task.assigned_to
        if recipient and recipient.email:
            send_mail(
                subject=f'Przypomnienie: termin zadania "{task.title}"',
                message=(
                    f'Cześć {recipient.username},\n\n'
                    f'Przypominamy, że zadanie "{task.title}" ma termin za 2 dni: {task.deadline}.\n'
                    f'Sprawdź w TickTask!'
                ),
                from_email=None,
                recipient_list=[recipient.email],
            )