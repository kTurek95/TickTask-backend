from django.db import models
from django.contrib.auth.models import User

class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    is_group = models.BooleanField(default=False)
    group_name = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Conversation {self.id}"

class ChatMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username}: {self.text[:20]}"
    

class ConversationSeen(models.Model):
    conversation = models.ForeignKey('Conversation', on_delete=models.CASCADE, related_name='seen')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('conversation', 'user')

    def __str__(self):
        return f"{self.user.username} saw {self.conversation.id} at {self.last_seen}"
