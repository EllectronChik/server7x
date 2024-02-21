from rest_framework import permissions    

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow only admin users to modify resources,
    while allowing read-only access to other users.
    """
    def has_permission(self, request, view):
        """
        Determine if the user has permission to access the view.

        Args:
            request (HttpRequest): The incoming HTTP request.
            view (Any): The view being accessed.

        Returns:
            bool: True if the user has permission, False otherwise.
        """
        if request.method in permissions.SAFE_METHODS:
            # Allow read-only access for safe methods (GET, HEAD, OPTIONS).
            return True
        # Allow modification only if the user is an admin.
        return bool(request.user and request.user.is_staff)


class IsAdminOrOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow admin users or object owners to modify resources,
    while allowing read-only access to other users.
    """
    def has_object_permission(self, request, view, obj):
        """
        Determine if the user has permission to modify the object.

        Args:
            request (HttpRequest): The incoming HTTP request.
            view (Any): The view being accessed.
            obj (Any): The object being accessed.

        Returns:
            bool: True if the user has permission, False otherwise.
        """
        if request.method in permissions.SAFE_METHODS:
            # Allow read-only access for safe methods (GET, HEAD, OPTIONS).
            return True
        # Allow modification if the user is the owner of the object or is an admin.
        return obj.user == request.user or bool(request.user and request.user.is_staff)


class CanEditMatchField(permissions.BasePermission):
    """
    Custom permission to allow editing of match fields by players or admin users.
    """
    def has_object_permission(self, request, view, obj):
        """
        Determine if the user has permission to edit the match field.

        Args:
            request (HttpRequest): The incoming HTTP request.
            view (Any): The view being accessed.
            obj (Any): The object being accessed.

        Returns:
            bool: True if the user has permission, False otherwise.
        """
        if request.method in permissions.SAFE_METHODS:
            # Allow read-only access for safe methods (GET, HEAD, OPTIONS).
            return True
        
        # Allow modification if the user is one of the players or is an admin.
        if request.user and obj.player_one and obj.player_two:
            if (request.user == obj.player_one.user) or (request.user == obj.player_two.user):
                return True
        return bool(request.user and request.user.is_staff)
