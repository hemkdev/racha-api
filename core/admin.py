from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.models import Booking, Court, User


class ProfileUserAdmin(UserAdmin):
    fieldsets = (*UserAdmin.fieldsets, ("Arena", {"fields": ("role", "phone")}))
    add_fieldsets = (*UserAdmin.add_fieldsets, ("Arena", {"fields": ("role", "phone")}))


admin.site.register(User, ProfileUserAdmin)
admin.site.register(Court)
admin.site.register(Booking)
