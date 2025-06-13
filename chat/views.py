from rest_framework import generics, permissions
from .models import ChatMessage, Conversation, ConversationSeen
from .serializers import ChatMessageSerializer, ConversationSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.utils.timezone import now
from rest_framework import status
from django.utils import timezone

class ChatMessageListCreateView(generics.ListCreateAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        conversation_id = self.kwargs['conversation_id']
        conversation = Conversation.objects.get(id=conversation_id)

        if self.request.user not in conversation.participants.all():
            return ChatMessage.objects.none()

        return conversation.messages.order_by('timestamp')

    def perform_create(self, serializer):
        conversation = Conversation.objects.get(id=self.kwargs['conversation_id'])
        serializer.save(sender=self.request.user, conversation=conversation)

        
class ConversationListCreateView(generics.ListCreateAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(participants=self.request.user)

    def perform_create(self, serializer):
        conversation = serializer.save()
        conversation.participants.add(*self.request.data.get('participants', []))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

        
        
class GetOrCreateConversationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        participants = request.data.get("participants")
        is_group = request.data.get("is_group", False)
        group_name = request.data.get("group_name", "")

        if not participants or len(participants) < 1:
            return Response({"error": "At least 1 participant required"}, status=400)

        participants = list(map(int, participants))
        # Dodaj aktualnego użytkownika do zestawu uczestników (automatycznie)
        participants.append(request.user.id)
        unique_participants = list(set(participants))  # usuwanie duplikatów

        users = User.objects.filter(id__in=unique_participants)
        if users.count() != len(unique_participants):
            return Response({"error": "Some users not found"}, status=404)

        if is_group:
            # Tworzenie nowej rozmowy grupowej
            new_convo = Conversation.objects.create(
                is_group=True,
                group_name=group_name
            )
            new_convo.participants.set(users)
            serializer = ConversationSerializer(new_convo, context={"request": request})
            return Response(serializer.data, status=201)

        else:
            if len(unique_participants) != 2:
                return Response({"error": "Exactly 2 participants required for private chat"}, status=400)

            participants_set = set(unique_participants)

            # Szukaj istniejącej rozmowy 1:1
            for convo in Conversation.objects.filter(is_group=False):
                convo_set = set(convo.participants.values_list("id", flat=True))
                if convo_set == participants_set:
                    serializer = ConversationSerializer(convo, context={"request": request})
                    return Response(serializer.data)

            # Nie znaleziono — utwórz nową
            new_convo = Conversation.objects.create(is_group=False)
            new_convo.participants.set(users)
            serializer = ConversationSerializer(new_convo, context={"request": request})
            return Response(serializer.data, status=201)


    
    
class UpdateLastSeenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, conversation_id):
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            if request.user not in conversation.participants.all():
                return Response({'error': 'Brak dostępu'}, status=status.HTTP_403_FORBIDDEN)

            seen_obj, _ = ConversationSeen.objects.get_or_create(
                conversation=conversation,
                user=request.user
            )

            seen_obj.last_seen = timezone.now()
            seen_obj.save()

            return Response({'status': 'Zaktualizowano'}, status=200)
        except Conversation.DoesNotExist:
            return Response({'error': 'Nie znaleziono rozmowy'}, status=404)

class UnreadMessageCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, conversation_id):
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            if request.user not in conversation.participants.all():
                return Response({'error': 'Brak dostępu'}, status=status.HTTP_403_FORBIDDEN)

            seen_obj, _ = ConversationSeen.objects.get_or_create(
                conversation=conversation,
                user=request.user
            )

            unread_count = conversation.messages.filter(
                timestamp__gt=seen_obj.last_seen or conversation.created_at
            ).exclude(sender=request.user).count()

            return Response({'unread': unread_count})
        except Conversation.DoesNotExist:
            return Response({'error': 'Nie znaleziono rozmowy'}, status=status.HTTP_404_NOT_FOUND)
        
        
class GroupConversationsView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(
            participants=self.request.user,
            is_group=True
        )
        

class SendMessageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, conversation_id):
        user = request.user
        text = request.data.get('text')

        if not text:
            return Response({'error': 'Text is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)

        if user not in conversation.participants.all():
            return Response({'error': 'Not a participant of this conversation'}, status=status.HTTP_403_FORBIDDEN)

        ChatMessage.objects.create(
            conversation=conversation,
            sender=user,
            text=text
        )

        return Response({'status': 'Message sent'}, status=status.HTTP_201_CREATED)


class ChatMessageDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, conversation_id):
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=404)

        if request.user not in conversation.participants.all():
            return Response({'error': 'Not a participant of this conversation'}, status=403)

        messages = ChatMessage.objects.filter(conversation=conversation).order_by('timestamp')
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)
