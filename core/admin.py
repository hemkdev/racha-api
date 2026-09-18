from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.models import Booking, Court, User

admin.site.register(User, UserAdmin)
admin.site.register(Court)
admin.site.register(Booking)
