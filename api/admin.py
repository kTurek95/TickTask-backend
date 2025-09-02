from django.contrib import admin
from .models import UserProfile, Group, GroupMembership, Task

# Register your models here.

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')  # pokazuje te pola w tabeli
    search_fields = ('user__username', 'role')  # umożliwia wyszukiwanie
    
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_completed', 'created_by', 'assigned_to', 'attachment')
    search_fields = ('user', 'title', 'created_by', 'assigned_to')
   
admin.site.register(Group)
admin.site.register(GroupMembership)