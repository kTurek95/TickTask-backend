from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics,viewsets, permissions
from .serializers import UserSerializer, NoteSerializer, TaskSerializer, ScheduleSerializer, CommentSerializer, ActivitySerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Note, Task, Schedule, Activity
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from .models import Comment
from django.utils import timezone
from collections import Counter
from .utils import log_activity

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Task.objects.all() if user.is_staff else Task.objects.filter(assigned_to=user)

    def get_serializer_context(self):
        return {"request": self.request}

    def perform_create(self, serializer):
        task = serializer.save(created_by=self.request.user)
        creator = self.request.user
        assigned_to = task.assigned_to

        # Logika aktywności:
        if creator == assigned_to:
            log_activity(creator, f"Utworzyłeś zadanie: {task.title}")
        else:
            log_activity(creator, f"Przydzieliłeś zadanie '{task.title}' dla {assigned_to.username}")
            log_activity(assigned_to, f"Otrzymałeś nowe zadanie: {task.title}")


class NoteListCreate(generics.ListCreateAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Note.objects.filter(author=user)

    def perform_create(self, serializer):
        if serializer.is_valid():
            serializer.save(author=self.request.user)
        else:
            print(serializer.errors)


class NoteDelete(generics.DestroyAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Note.objects.filter(author=user)


class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    
    
class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        base_qs = Task.objects.all() if user.is_staff else Task.objects.filter(assigned_to=user)
        return base_qs.order_by('deadline').reverse()


    def get_serializer_context(self):
        return {"request": self.request}

    def perform_create(self, serializer):
        task = serializer.save(created_by=self.request.user)
        creator = self.request.user
        assigned_to = task.assigned_to

        # Logika aktywności:
        if creator == assigned_to:
            # Zadanie przydzielone samemu sobie
            log_activity(creator, f"Utworzyłeś zadanie: {task.title}")
        else:
            # Dla tworzącego (admina, lidera itp.)
            log_activity(creator, f"Przydzieliłeś zadanie '{task.title}' dla {assigned_to.username}")
            
            # Dla odbiorcy zadania — tu dodajemy source_user
            log_activity(
                assigned_to,
                f"Otrzymałeś nowe zadanie: {task.title}",
                source_user=creator
        )
            
    def perform_update(self, serializer):
        old_task = self.get_object()
        old_data = {
            "title": old_task.title,
            "description": old_task.description,
            "deadline": old_task.deadline,
            "is_completed": old_task.is_completed,
            "priority": old_task.priority,
        }

        updated_task = serializer.save()
        changes = []

        if old_data["title"] != updated_task.title:
            changes.append("zmieniono tytuł")

        if old_data["description"] != updated_task.description:
            changes.append("zmieniono opis")

        if old_data["deadline"] != updated_task.deadline:
            changes.append("zmieniono termin")

        if old_data["is_completed"] != updated_task.is_completed:
            before = "ukończone" if old_data["is_completed"] else "nieukończone"
            after = "ukończone" if updated_task.is_completed else "nieukończone"
            changes.append(f"zmieniono status z {before} na {after}")

        if old_data["priority"] != updated_task.priority:
            changes.append(f"zmieniono priorytet z {old_data['priority']} na {updated_task.priority}")

        if changes:
            log_activity(self.request.user, f"Zadanie '{updated_task.title}' – {', '.join(changes)}")

            if updated_task.assigned_to != self.request.user:
                log_activity(updated_task.assigned_to, f"Zadanie '{updated_task.title}' zostało zmodyfikowane – {', '.join(changes)}")

                
    def perform_destroy(self, instance):
        log_activity(self.request.user, f"Usunąłeś zadanie: '{instance.title}'")
        instance.delete()


class ScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = ScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Schedule.objects.filter(user=self.request.user).order_by('date')
    
class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Terminy: swoje lub wszystkie
        if user.is_staff:
            terminy = Schedule.objects.count()
            uzytkownicy = User.objects.count()
        else:
            terminy = Schedule.objects.filter(user=user).count()
            uzytkownicy = None  # albo 0 lub nie zwracać

        return Response({
            "terminy": terminy,
            "uzytkownicy": uzytkownicy,
        })
    
class UserListView(generics.ListAPIView):
    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print("=== DEBUG USER ===")
        print("Username:", user.username)
        print("Is staff:", user.is_staff)

        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff
        })


class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        task_id = self.kwargs['task_id']
        return Comment.objects.filter(task_id=task_id).order_by('created_at')

    def perform_create(self, serializer):
        task_id = self.kwargs['task_id']
        try:
            task = Task.objects.get(id=task_id)
            serializer.save(author=self.request.user, task=task)
            log_activity(
                self.request.user,
                f"Dodałeś komentarz do zadania: '{task.title}'"
            )
        except Task.DoesNotExist:
            serializer.save(author=self.request.user, task_id=task_id)


class TaskStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()

        # ✅ Automatyczna zmiana na "po_terminie", tylko dla NIEukończonych zadań
        Task.objects.filter(
            assigned_to=user,
            is_completed=False,
            deadline__lt=now
        ).exclude(status="overdue").exclude(status="completed").update(status="overdue")

        assigned_tasks = Task.objects.filter(assigned_to=user)

        total = assigned_tasks.count()
        completed = assigned_tasks.filter(status="completed").count()
        in_progress = assigned_tasks.filter(status="in_progress").count()
        overdue = assigned_tasks.filter(status="overdue").count()
        upcoming = assigned_tasks.filter(status="upcoming").count()

        priority_counts = dict(Counter(assigned_tasks.values_list("priority", flat=True)))

        return Response({
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "overdue": overdue,
            "upcoming": upcoming,
            "priority_stats": priority_counts
        })
        

class ActivityListView(generics.ListAPIView):
    serializer_class = ActivitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if self.request.query_params.get("all") == "true" and user.is_staff:
            return Activity.objects.exclude(user=user).order_by("-created_at")
        return Activity.objects.filter(user=user).order_by("-created_at")
    
    
class TaskSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get('user_id')
        users = User.objects.all()

        if user_id:
            users = users.filter(id=user_id)

        data = []
        for user in users:
            user_tasks = Task.objects.filter(assigned_to=user)
            total = user_tasks.count()
            completed = user_tasks.filter(is_completed=True).count()
            overdue = user_tasks.filter(status="overdue").count()
            upcoming = user_tasks.filter(status="upcoming").count()
            in_progress = user_tasks.filter(status="in_progress").count()
            completed = user_tasks.filter(status="completed").count()

            priority_stats = {
                "Wysoki": user_tasks.filter(priority="Wysoki").exclude(status="completed").count(),
                "Średni": user_tasks.filter(priority="Średni").exclude(status="completed").count(),
                "Niski": user_tasks.filter(priority="Niski").exclude(status="completed").count(),
            }

            data.append({
                "id": user.id,
                "username": user.username,
                "total": total,
                "completed": completed,
                "overdue": overdue,
                "upcoming": upcoming,
                "in_progress": in_progress,
                "priority_stats": priority_stats,
            })

        return Response(data)