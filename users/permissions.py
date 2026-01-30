from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOrganizerOrReadOnly(BasePermission):
    """
    Organizers can create/update/delete.
    Others can only read.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        return (
            request.user.is_authenticated and
            request.user.role == 'organizer'
        )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        
        # Only the organizer who created the event can edit/delete it
        # Assuming the object has an 'organizer' attribute
        return getattr(obj, 'organizer', None) == request.user
