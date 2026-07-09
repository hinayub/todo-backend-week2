from rest_framework.permissions import BasePermission


def is_admin(user):
    return user.is_authenticated and getattr(user, "profile", None) and user.profile.role == "admin"


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)


class IsOwnerOrAdmin(BasePermission):
    """Object-level check: the request user owns the object, or is an admin."""

    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id or is_admin(request.user)
