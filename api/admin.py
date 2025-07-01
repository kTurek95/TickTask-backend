from django.contrib import admin
from .models import UserProfile, Group, GroupMembership

# Register your models here.

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')  # pokazuje te pola w tabeli
    search_fields = ('user__username', 'role')  # umożliwia wyszukiwanie
    

admin.site.register(Group)
admin.site.register(GroupMembership)