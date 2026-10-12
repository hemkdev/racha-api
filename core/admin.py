from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.models import Booking, Court, Order, Sport, User


class ProfileUserAdmin(UserAdmin):
    fieldsets = (*UserAdmin.fieldsets, ("Arena", {"fields": ("role", "phone")}))
    add_fieldsets = (*UserAdmin.add_fieldsets, ("Arena", {"fields": ("role", "phone")}))


class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "court",
        "starts_at",
        "ends_at",
        "created_by",
        "status",
    )
    list_filter = ("status", "court", "order__user", "created_by")
    list_select_related = ("court", "order__user", "created_by")
    search_fields = ("court__name", "order__user__username", "created_by__username")


class CourtAdminForm(forms.ModelForm):
    sports = forms.MultipleChoiceField(
        choices=Sport.choices,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Court
        fields = "__all__"


class CourtAdmin(admin.ModelAdmin):
    form = CourtAdminForm
    list_display = ("id", "name", "tier", "hour_price", "is_active", "sports")
    list_filter = ("tier", "is_active")
    search_fields = ("name",)


admin.site.register(User, ProfileUserAdmin)
admin.site.register(Court, CourtAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Order)
