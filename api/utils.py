from .models import Activity

def log_activity(user, action, source_user=None):
    Activity.objects.create(user=user, action=action, source_user=source_user)
