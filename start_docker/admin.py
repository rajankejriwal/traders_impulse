from django.contrib import admin

from start_docker.models import Instance


class InstanceAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "container_id", "logs_link"]

    def logs_link(self, obj):
        from django.utils.html import format_html

        return format_html(
            '<a href="{}" target="_blank">{}</a>', obj.logs, obj.container_id
        )

    def get_queryset(self, request):
        return super().get_queryset(request)

    logs_link.short_description = "logs"


admin.site.register(Instance, InstanceAdmin)
