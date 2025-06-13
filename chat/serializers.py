from rest_framework import serializers
from .models import ChatMessage, Conversation
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.ReadOnlyField(source='sender.username')
    conversation = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'conversation', 'sender_username', 'text', 'timestamp']



class ConversationSerializer(serializers.ModelSerializer):
    participants = UserSerializer(many=True, read_only=True)
    other_user = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'participants', 'created_at', 'other_user', 'is_group', 'group_name']

    def get_other_user(self, obj):
        if obj.is_group:
            return None
        user = self.context['request'].user
        other = obj.participants.exclude(id=user.id).first()
        return UserSerializer(other).data if other else None

