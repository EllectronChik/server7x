from rest_framework import permissions


# class isOwnerOrAdminOrReadOnly(permissions.BasePermission):
#     def has_object_permission(self, request, view, obj):
#         if request.method in permissions.SAFE_METHODS:
#             return True
#         if obj.user == request.user:
#             return True
#         if bool(request.user and request.user.is_staff):
#             return True
#         return False
    
#     def has_permission(self, request, view):
#         if request.method in permissions.SAFE_METHODS:
#             return True
#         return bool(request.user and request.user.is_staff)
    

class isAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)
    

class isOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class isAdminOrOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user or bool(request.user and request.user.is_staff)


class canEditMatchField(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if request.user and obj.player_one and obj.player_two:
            if (request.user == obj.player_one.user) or (request.user == obj.player_two.user):
                return True
        return bool(request.user and request.user.is_staff)
    

class CanPostOrIsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'POST':
            return True
        return bool(request.user and request.user.is_staff)
    
    def has_object_permission(self, request, view, obj):
        return bool(request.user and request.user.is_staff)