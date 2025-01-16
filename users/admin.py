from django.contrib import admin
from users.models import UserConfig


class UserConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "server_id")


admin.site.register(UserConfig, UserConfigAdmin)
