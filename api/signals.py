from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile
from django.core.mail import send_mail
from .models import Comment

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=Comment)
def notify_comment(sender, instance, created, **kwargs):
    if created:
        task = instance.task
        creator = instance.author  # ← bo w Comment to jest `author`!

        # Lider napisał → powiadom przypisanego
        # Członek napisał → powiadom lidera

        if creator == task.created_by:
            recipient = task.assigned_to
        else:
            recipient = task.created_by

        if recipient and recipient.email:
            send_mail(
                subject=f'Nowy komentarz do zadania: {task.title}',
                message=(
                    f'Cześć {recipient.username},\n\n'
                    f'{creator.username} dodał komentarz do zadania "{task.title}":\n'
                    f'"{instance.content}"\n\n'
                    f'Sprawdź w TickTask!'
                ),
                from_email='noreply@inqse.com',
                recipient_list=[recipient.email],
                fail_silently=False
            )
