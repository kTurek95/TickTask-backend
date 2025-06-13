from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, ScheduleViewSet, NoteListCreate, NoteDelete, UserListView, MeView, CommentListCreateView, TaskStatsView, ActivityListView, DashboardStatsView, TaskSummaryView

router = DefaultRouter()
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'schedules', ScheduleViewSet, basename='schedule')

urlpatterns = [
    path('', include(router.urls)),
    path("notes/", NoteListCreate.as_view(), name="note-list"),
    path("notes/delete/<int:pk>/", NoteDelete.as_view(), name="delete-note"),
    path("users/", UserListView.as_view(), name="user-list"),
    path("me/", MeView.as_view(), name="me"),
    path('tasks/<int:task_id>/comments/', CommentListCreateView.as_view(), name='task-comments'),
    path("tasks-stats/", TaskStatsView.as_view()),
    path("activities/", ActivityListView.as_view(), name="activity-list"),
    path("dashboard-stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("summary-tasks/", TaskSummaryView.as_view()),
]
