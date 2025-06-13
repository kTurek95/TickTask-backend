from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Note(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")

    def __str__(self):
        return self.title
    
PRIORITY_CHOICES = [
    ('Wysoki', 'Wysoki'),
    ('Średni', 'Średni'),
    ('Niski', 'Niski'),
]

STATUS_CHOICES = [
        ('in_progress', 'W toku'),
        ('completed', 'Ukończone'),
        ('overdue', 'Po terminie'),
        ('upcoming', 'Nadchodzące'),
    ]

class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, default=1)
    deadline = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="Średni")  # <- DODANE
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_tasks')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')

    def __str__(self):
        return f"{self.title} ({self.user.username})"
    
    
    def save(self, *args, **kwargs):
        now = timezone.now()
        if self.is_completed:
            self.status = 'completed'
        elif self.deadline:
            if self.deadline < now:
                self.status = 'overdue'
            else:
                self.status = 'upcoming'
        else:
            self.status = 'in_progress'

        super().save(*args, **kwargs)

    
class Schedule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schedules')
    name = models.CharField(max_length=255)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.date}) - {self.user.username}"
    

class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Activity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    action = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    source_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='activities_made_by'
    )

    def __str__(self):
        return f"{self.user.username} - {self.action} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
