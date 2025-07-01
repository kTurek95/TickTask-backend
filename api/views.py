from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics,viewsets, permissions, filters
from .serializers import UserSerializer, NoteSerializer, TaskSerializer, ScheduleSerializer, CommentSerializer, ActivitySerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Note, Task, Schedule, Activity, GroupMembership
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from .models import Comment
from django.utils import timezone
from collections import Counter
from .utils import log_activity
from rest_framework import status

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
    
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['deadline', 'priority', 'status']  # albo inne pola zadań
    ordering = ['deadline']  # domyślne

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Task.objects.all()

        if hasattr(user, "userprofile") and user.userprofile.role == "leader":
            # Grupy, gdzie user jest leaderem
            user_group_ids = GroupMembership.objects.filter(
                user=user
            ).values_list('group_id', flat=True)

            # Userzy w tych grupach
            group_user_ids = GroupMembership.objects.filter(
                group_id__in=user_group_ids
            ).values_list('user_id', flat=True)

            return Task.objects.filter(
                assigned_to__id__in=group_user_ids
            )

        # Zwykły user
        return Task.objects.filter(assigned_to=user)

    def get_serializer_context(self):
        return {"request": self.request}

    def create(self, request, *args, **kwargs):
        creator = request.user
        assigned_to_ids = request.data.get("assigned_to_ids", [])

        if isinstance(assigned_to_ids, str):
            assigned_to_ids = [assigned_to_ids]

        assigned_to_ids = [int(uid) for uid in assigned_to_ids]

        tasks = []

        if assigned_to_ids:
            for user_id in assigned_to_ids:
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)

                assigned_to_user = User.objects.get(id=user_id)

                task = serializer.save(
                    created_by=creator,
                    assigned_to=assigned_to_user,
                    user=creator
                )

                tasks.append(task)  # <-- DODAJESZ DO LISTY!

                if creator == assigned_to_user:
                    # Tylko jeśli tworzysz dla siebie
                    log_activity(user=creator, action=f"Utworzyłeś zadanie: {task.title}")

                if creator != assigned_to_user:
                    # Logujesz przydzielenie dla Ciebie (leader)
                    log_activity(
                        user=creator,
                        action=f"Przydzieliłeś zadanie '{task.title}' dla {assigned_to_user.username}"
                    )
                    # Odbiorca dostaje swój log
                    log_activity(
                        user=assigned_to_user,
                        source_user=creator,
                        action=f"Przydzielono Ci zadanie: {task.title}"
                    )

            return Response(self.get_serializer(tasks, many=True).data, status=status.HTTP_201_CREATED)

        else:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            task = serializer.save(
                created_by=creator,
                assigned_to=creator,
                user=creator
            )

            log_activity(user=creator, action=f"Utworzyłeś zadanie: {task.title}")

            return Response(self.get_serializer(task).data, status=status.HTTP_201_CREATED)


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
        # if user.is_staff:
        terminy = Schedule.objects.count()
        uzytkownicy = User.objects.count()
        # else:
        #     terminy = Schedule.objects.filter(user=user).count()
        #     uzytkownicy = None  # albo 0 lub nie zwracać

        return Response({
            "terminy": terminy,
            "uzytkownicy": uzytkownicy,
        })
    
class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print("=== DEBUG USER ===")
        print("Username:", request.user.username)
        print("Is staff:", request.user.is_staff)
        print("UserProfile:", getattr(request.user, "userprofile", "BRAK"))

        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print("=== DEBUG USER ===")
        print("Username:", user.username)
        print("Is staff:", user.is_staff)

        serializer = UserSerializer(user)
        return Response(serializer.data)


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
        

# class ActivityListView(generics.ListAPIView):
#     serializer_class = ActivitySerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         user = self.request.user
#         is_admin = user.is_staff
#         is_leader = hasattr(user, "userprofile") and user.userprofile.role == "leader"

#         if self.request.query_params.get("all") == "true" and is_admin:
#             return Activity.objects.all().order_by("-created_at")

#         if is_leader:
#             # znajdź grupy leadera
#             group_ids = GroupMembership.objects.filter(
#                 user=user, role="leader"
#             ).values_list("group_id", flat=True)

#             # znajdź userów z tych grup
#             group_user_ids = GroupMembership.objects.filter(
#                 group_id__in=group_ids
#             ).values_list("user_id", flat=True)

#             return Activity.objects.filter(
#                 user__id__in=group_user_ids
#             ).order_by("-created_at")

#         # zwykły user
#         return Activity.objects.filter(user=user).order_by("-created_at")


class MyActivityListView(generics.ListAPIView):
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff and self.request.query_params.get("all") == "true":
            return Activity.objects.all().order_by("-created_at")

        return Activity.objects.filter(user=user).order_by("-created_at")



class GroupActivityListView(generics.ListAPIView):
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff and self.request.query_params.get("all") == "true":
            return Activity.objects.exclude(user=user).order_by("-created_at")

        is_leader = hasattr(user, "userprofile") and user.userprofile.role == "leader"

        if is_leader:
            group_ids = GroupMembership.objects.filter(
                user=user, role="leader"
            ).values_list("group_id", flat=True)

            group_user_ids = GroupMembership.objects.filter(
                group_id__in=group_ids
            ).values_list("user_id", flat=True)

            return Activity.objects.filter(
                user__id__in=group_user_ids
            ).exclude(user=user).order_by("-created_at")

        return Activity.objects.none()



    
    
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
    

class VisibleUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.is_staff:
            users = User.objects.all()
        elif hasattr(user, "userprofile") and user.userprofile.role == 'leader':
            group_ids = GroupMembership.objects.filter(
                user=user, role='leader'
            ).values_list('group_id', flat=True)

            users = User.objects.filter(
                groupmembership__group_id__in=group_ids
            ).distinct()
        else:
            users = User.objects.none()

        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


class CompletedTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # 🔑 Poprawiony warunek:
        qs = Task.objects.filter(status="completed")

        if user.is_staff:
            return qs

        if hasattr(user, "userprofile") and user.userprofile.role == "leader":
            group_ids = GroupMembership.objects.filter(
                user=user, role="leader"
            ).values_list("group_id", flat=True)

            group_user_ids = GroupMembership.objects.filter(
                group_id__in=group_ids
            ).values_list("user_id", flat=True)

            return qs.filter(assigned_to__id__in=group_user_ids)

        return qs.filter(assigned_to=user)
