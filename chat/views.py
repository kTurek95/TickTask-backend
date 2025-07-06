from rest_framework import generics, permissions, viewsets
from .models import ChatMessage, Conversation, ConversationSeen
from .serializers import ChatMessageSerializer, ConversationSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.utils.timezone import now
from rest_framework import status
from django.utils import timezone
from django.core.mail import send_mail


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
        serializer.save(
            sender=self.request.user,
            conversation=conversation
        )
        
        message = serializer.save(
            sender=self.request.user,
            conversation=conversation
        )

        # 🔑 Wykluczasz nadawcę!
        recipients = conversation.participants.exclude(id=self.request.user.id)

        for recipient in recipients:
            if recipient.email:
                send_mail(
                    subject="📬 Nowa wiadomość w TickTask",
                    message=(
                        f"Cześć {recipient.username},\n\n"
                        f"Masz nową wiadomość od {self.request.user.username}:\n\n"
                        f"\"{message.text}\"\n\n"
                        f"Zaloguj się do TickTask, aby odpowiedzieć!"
                    ),
                    from_email='noreply@inqse.com',
                    recipient_list=[recipient.email],
                    fail_silently=False
                )
        
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
        participants.append(request.user.id)  # dodaj siebie
        unique_participants = list(set(participants))

        users = User.objects.filter(id__in=unique_participants)
        if users.count() != len(unique_participants):
            return Response({"error": "Some users not found"}, status=404)

        if is_group:
            # 🔑 Tworzenie nowej rozmowy grupowej z created_by
            new_convo = Conversation.objects.create(
                is_group=True,
                group_name=group_name,
                created_by=request.user  # <- to jest KLUCZ!
            )
            new_convo.participants.set(users)
            serializer = ConversationSerializer(new_convo, context={"request": request})
            return Response(serializer.data, status=201)

        else:
            if len(unique_participants) != 2:
                return Response({"error": "Exactly 2 participants required for private chat"}, status=400)

            participants_set = set(unique_participants)

            for convo in Conversation.objects.filter(is_group=False):
                convo_set = set(convo.participants.values_list("id", flat=True))
                if convo_set == participants_set:
                    serializer = ConversationSerializer(convo, context={"request": request})
                    return Response(serializer.data)

            new_convo = Conversation.objects.create(
                is_group=False,
                created_by=request.user  # możesz dać to t  eż tu dla spójności
            )
            new_convo.participants.set(users)
            serializer = ConversationSerializer(new_convo, context={"request": request})
            return Response(serializer.data, status=201)

class GroupViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.filter(is_group=True)
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        if group.created_by_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "Brak uprawnień"}, status=403)
        group.delete()
        return Response(status=204)

    
    
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

        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if user not in conversation.participants.all():
            return Response(
                {'error': 'Not a participant of this conversation'},
                status=status.HTTP_403_FORBIDDEN
            )

        # ✅ UŻYJ SERIALIZERA!
        serializer = ChatMessageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(sender=user, conversation=conversation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        conversation = self.get_object()

        if not conversation.is_group:
            return Response({"error": "Nie można usuwać czatu prywatnego."}, status=400)

        if request.user.is_staff or request.user in conversation.participants.all():
            conversation.delete()
            return Response(status=204)

        return Response({"error": "Brak uprawnień."}, status=403)