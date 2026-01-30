from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from .models import CustomUser

@receiver(post_save, sender=CustomUser)
def assign_role_group(sender, instance, created, **kwargs):
    """
    Assign user to a Django Group based on their 'role' field.
    This ensures they inherit permissions defined for that role.
    """
    if created or instance._state.adding:
        # Map 'role' choices to Group names
        # 'organizer' -> 'Organizer'
        # 'admin' -> 'Admin'
        # 'attendee' -> 'Attendee'
        
        group_name = instance.role.capitalize()
        
        try:
            group = Group.objects.get(name=group_name)
            instance.groups.add(group)
        except Group.DoesNotExist:
            pass
            
    # Optional: If role changes, update groups?
    # For now, let's stick to initial assignment or manual updates.
