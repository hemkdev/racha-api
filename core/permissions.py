from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role


class IsStaffRoleOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role == Role.STAFF
