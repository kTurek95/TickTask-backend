from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Note, Task, Schedule, Comment, Activity


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "password", "email"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        print(validated_data)
        user = User.objects.create_user(**validated_data)
        return user


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "title", "content", "created_at", "author"]
        extra_kwargs = {"author": {"read_only": True}}
        

STATUS_LABELS = {
    "in_progress": "W toku",
    "completed": "Ukończone",
    "overdue": "Po terminie",
    "upcoming": "Nadchodzące",
    "all": "Wszystkie"
    }

class TaskSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    assigned_to = serializers.StringRelatedField(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="assigned_to", write_only=True, required=False
    )
    recent_comments = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id", "user", "title", "description",
            "is_completed", "created_at", "deadline",
            "priority", "created_by", "assigned_to", "assigned_to_id", 'recent_comments', 'status'
        ]
        read_only_fields = ["id", "created_at", "created_by", "assigned_to", "user"]

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user

        # Przypisz zadanie do siebie, jeśli nie jest podane assigned_to
        if not user.is_staff or "assigned_to" not in validated_data:
            validated_data["assigned_to"] = user

        validated_data["user"] = user
        validated_data["created_by"] = user

        return super().create(validated_data)
    
    def validate_status(self, value):
        allowed_statuses = list(STATUS_LABELS.keys())
        if value not in allowed_statuses:
            raise serializers.ValidationError("Nieprawidłowy status zadania.")
        return value
    

    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = request.user

        old_status = instance.status
        new_status = validated_data.get("status")

        updated_task = super().update(instance, validated_data)

        if new_status and new_status != old_status:
            old_label = STATUS_LABELS.get(old_status, old_status)
            new_label = STATUS_LABELS.get(new_status, new_status)

            Activity.objects.create(
                user=instance.assigned_to,
                source_user=user,
                action=(
                    f"Status zadania '{instance.title}' został zmieniony "
                    f"z '{old_label}' na '{new_label}'."
                )
            )

        return updated_task
    
    def get_recent_comments(self, obj):
        recent = obj.comments.order_by('-created_at')[:2]
        return [
            {
                'content': comment.content,
                'author': comment.author.username,
                'created_at': comment.created_at
            }
            for comment in recent
        ]


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = ['id', 'user', 'name', 'date', 'time', 'notes']
        read_only_fields = ['id', 'user']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    

class CommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'task', 'author', 'author_username', 'content', 'created_at']
        read_only_fields = ['id', 'author', 'created_at', 'task']


class ActivitySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    source_user = serializers.CharField(source="source_user.username", read_only=True)

    class Meta:
        model = Activity
        fields = ["id", "action", "created_at", "username", "source_user"]