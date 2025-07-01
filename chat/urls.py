from django.urls import path
from .views import ChatMessageListCreateView, ConversationListCreateView, GetOrCreateConversationView, UnreadMessageCountView, UpdateLastSeenView, GroupConversationsView
from rest_framework.routers import DefaultRouter
from .views import SendMessageView, ChatMessageDetailView, ConversationViewSet

urlpatterns = [
    path('chat/<int:conversation_id>/messages/', ChatMessageListCreateView.as_view(), name='chat-messages'),
    path('chat/<int:conversation_id>/', ChatMessageDetailView.as_view(), name='chat-detail'),  # <-- DODAJ TO
    path('chat/<int:conversation_id>/send/', SendMessageView.as_view(), name='chat-send'),     # <-- I TO

    path('chat/<int:conversation_id>/seen/', UpdateLastSeenView.as_view()),
    path('chat/<int:conversation_id>/unread/', UnreadMessageCountView.as_view(), name='unread-messages'),

    path("conversations/", ConversationListCreateView.as_view(), name="conversation-list-create"),
    path("conversations/get_or_create/", GetOrCreateConversationView.as_view()),
    path("conversations/groups/", GroupConversationsView.as_view(), name="group-conversations"),
]

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')

urlpatterns += router.urls

