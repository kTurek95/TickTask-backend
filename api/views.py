from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics,viewsets, permissions, filters, decorators
from .serializers import UserSerializer, NoteSerializer, TaskSerializer, ScheduleSerializer, CommentSerializer, ActivitySerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Note, Task, Schedule, Activity, GroupMembership
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Comment
from django.utils import timezone
from collections import Counter
from .utils import log_activity
from rest_framework import status
from django.core.mail import send_mail
from api.pagination import StandardResultsSetPagination
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.utils.dateparse import parse_date
from django.core.files.storage import default_storage
from rest_framework.decorators import action
from django.db.models import Count, Q


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
    pagination_class = None
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
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
                
                print("Assigned to IDs:", assigned_to_ids)
                print("Sending mail to:", assigned_to_user.email)

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
                    
                if assigned_to_user.email:
                    if creator == assigned_to_user:
                        # Przypadek: przypisujesz SAM SOBIE
                        msg = (
                            f'Cześć {assigned_to_user.username},\n\n'
                            f'Przypisałeś sobie nowe zadanie: "{task.title}".\n'
                            f'Sprawdź w TickTask!'
                        )
                    else:
                        # Przypadek: lider przypisuje KOMUŚ
                        msg = (
                            f'Cześć {assigned_to_user.username},\n\n'
                            f'Lider {creator.username} przypisał Ci nowe zadanie: "{task.title}".\n'
                            f'Sprawdź w TickTask!'
                        )

                    send_mail(
                        subject=f'Nowe zadanie: {task.title}',
                        message=msg,
                        from_email='noreply@inqse.com',
                        recipient_list=[assigned_to_user.email],
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
            "priority": old_task.priority,
            "status": old_task.status,  # <-- DODAJ TO!
        }

        updated_task = serializer.save()
        changes = []

        if old_data["title"] != updated_task.title:
            changes.append("zmieniono tytuł")
        if old_data["description"] != updated_task.description:
            changes.append("zmieniono opis")
        if old_data["deadline"] != updated_task.deadline:
            changes.append("zmieniono termin")
        STATUS_LABELS = {
            "in_progress": "W toku",
            "completed": "Ukończone",
            "overdue": "Po terminie",
            "upcoming": "Nadchodzące",
        }

        if old_data["status"] != updated_task.status:
            before_status = old_data["status"]
            after_status = updated_task.status

            pretty_before = STATUS_LABELS.get(before_status, before_status)
            pretty_after = STATUS_LABELS.get(after_status, after_status)

            changes.append(f"zmieniono status z {pretty_before} na {pretty_after}")

            changer = self.request.user

            if changer == updated_task.created_by:
                recipient = updated_task.assigned_to
            else:
                recipient = updated_task.created_by

            if recipient and recipient.email:
                send_mail(
                    subject=f'Status zadania zmieniony: {updated_task.title}',
                    message=(
                        f'Cześć {recipient.username},\n\n'
                        f'{changer.username} zmienił status zadania "{updated_task.title}" '
                        f'z {pretty_before} na {pretty_after}.\n'
                        f'Sprawdź w TickTask!'
                    ),
                    from_email=None,
                    recipient_list=[recipient.email],
                )

    def perform_destroy(self, instance):
        log_activity(self.request.user, f"Usunąłeś zadanie: '{instance.title}'")
        instance.delete()
        
    @action(detail=True, methods=["delete"], url_path="attachment")
    def delete_attachment(self, request, pk=None):
        task = self.get_object()

        try:
            f = task.attachment  # FieldFile
            # nic nie ma -> OK
            if not f or not getattr(f, "name", None):
                return Response(status=status.HTTP_204_NO_CONTENT)

            path = f.name  # UŻYWAMY f.name (relatywnej ścieżki), NIE f.path

            # spróbuj usunąć fizyczny plik, ale nie rób z tego błędu
            try:
                if default_storage.exists(path):
                    default_storage.delete(path)
            except Exception as e_storage:
                logger.warning("Storage delete warning for %s: %r", path, e_storage)

            # wyczyść pole i zapisz TYLKO to pole
            task.attachment = None
            task.save(update_fields=["attachment"])

            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            # pełny log do konsoli serwera + zwrot diagnostyki (tymczasowo)
            logger.exception("Attachment delete failed for task %s", task.pk)
            return Response(
                {"detail": f"delete_failed: {type(e).__name__}: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            
    # @action(detail=False, methods=["get"], url_path="metrics")
    # def metrics(self, request):
    #     """
    #     Zwraca metryki dla użytkownika:
    #     - total: liczba wszystkich zadań
    #     - completed: ukończone
    #     - upcoming: nieukończone z deadlinem w przyszłości
    #     - overdue: nieukończone z deadlinem w przeszłości
    #     - completion_rate: % ukończenia (0–100)
    #     Można podać ?user_id=123 (np. dla leadera/admina).
    #     """
    #     user = request.user
    #     user_id = request.query_params.get("user_id")
    #     if not user_id:
    #         user_id = user.id

    #     # Jeśli masz uprawnienia/role, możesz tu dodać walidację czy user
    #     # może oglądać metryki innego usera.
    #     qs = Task.objects.filter(assigned_to_id=user_id)

    #     now = timezone.now()
    #     agg = qs.aggregate(
    #         total=Count("id"),
    #         completed=Count("id", filter=Q(is_completed=True)),
    #         upcoming=Count("id", filter=Q(is_completed=False, deadline__gte=now)),
    #         overdue=Count("id", filter=Q(is_completed=False, deadline__lt=now)),
    #     )

    #     total = agg["total"] or 0
    #     completed = agg["completed"] or 0
    #     rate = round((completed / total) * 100, 1) if total else 0.0

    #     return Response({
    #         "user_id": int(user_id),
    #         "total": total,
    #         "completed": completed,
    #         "upcoming": agg["upcoming"] or 0,
    #         "overdue": agg["overdue"] or 0,
    #         "completion_rate": rate,
    #     })


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

# Jeśli nie masz – standardowa paginacja DRF
# class StandardResultsSetPagination(PageNumberPagination):
#     page_size = 10
#     page_size_query_param = "page_size"

def apply_activity_filters(qs, request):
    """
    Wspólne filtrowanie dla list aktywności.
    Oczekiwane query params:
      - action_icontains: fragment opisu akcji (np. 'Utworzyłeś zadanie')
      - date_from: 'YYYY-MM-DD'
      - date_to  : 'YYYY-MM-DD'
      - username : nazwa użytkownika (dla leader/admin; dla "my-activities" zwykle zbędne)
    """
    qp = request.query_params

    action_icontains = qp.get("action_icontains")
    username = qp.get("username")
    date_from = qp.get("date_from")
    date_to = qp.get("date_to")

    if action_icontains:
        qs = qs.filter(action__icontains=action_icontains)

    if username:
        qs = qs.filter(user__username=username)

    # Parsowanie dat – filtrujemy po komponencie DATE stempla czasowego
    df = parse_date(date_from) if date_from else None
    dt = parse_date(date_to) if date_to else None
    if df:
        qs = qs.filter(created_at__date__gte=df)
    if dt:
        qs = qs.filter(created_at__date__lte=dt)

    return qs


class MyActivityListView(generics.ListAPIView):
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user

        if user.is_staff and self.request.query_params.get("all") == "true":
            qs = Activity.objects.all()
        else:
            qs = Activity.objects.filter(user=user)

        qs = qs.select_related("user")
        qs = apply_activity_filters(qs, self.request)
        return qs.order_by("-created_at")


class GroupActivityListView(generics.ListAPIView):
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user

        if user.is_staff and self.request.query_params.get("all") == "true":
            qs = Activity.objects.exclude(user=user)
        else:
            # leader: tylko aktywności użytkowników z jego grup
            is_leader = hasattr(user, "userprofile") and user.userprofile.role == "leader"
            if is_leader:
                group_ids = GroupMembership.objects.filter(
                    user=user, role="leader"
                ).values_list("group_id", flat=True)

                group_user_ids = GroupMembership.objects.filter(
                    group_id__in=group_ids
                ).values_list("user_id", flat=True)

                qs = Activity.objects.filter(user__id__in=group_user_ids).exclude(user=user)
            else:
                qs = Activity.objects.none()

        qs = qs.select_related("user")
        qs = apply_activity_filters(qs, self.request)
        return qs.order_by("-created_at")

    
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
    
    
class ActivityUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        usernames = (
            Activity.objects.filter(user__isnull=False)
            .values_list("user__username", flat=True)
            .distinct()
            .order_by("user__username")
        )
        return Response(list(usernames))
