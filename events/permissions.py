from rest_framework.permissions import BasePermission

class IsOrganizerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ['GET']:
            return True
        return request.user.role == 'organizer'