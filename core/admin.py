from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.models import Booking, Court, User


class ProfileUserAdmin(UserAdmin):
    fieldsets = (*UserAdmin.fieldsets, ("Arena", {"fields": ("role", "phone")}))
    add_fieldsets = (*UserAdmin.add_fieldsets, ("Arena", {"fields": ("role", "phone")}))


class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "court",
        "user",
        "starts_at",
        "ends_at",
        "created_by",
        "status",
    )
    list_filter = ("status", "court", "user")
    list_select_related = ("court", "user", "created_by")
    search_fields = ("court__name", "user__username", "created_by__username")


admin.site.register(User, ProfileUserAdmin)
admin.site.register(Court)
admin.site.register(Booking, BookingAdmin)
