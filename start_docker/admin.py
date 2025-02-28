import docker

from django.contrib import admin
from django.contrib import messages

from start_docker.models import Instance


class InstanceAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "container_id", "logs_link"]
    actions = ["delete_docker"]

    def logs_link(self, obj):
        from django.utils.html import format_html

        return format_html(
            '<a href="{}" target="_blank">{}</a>', obj.logs, obj.container_id
        )

    logs_link.short_description = "logs"

    def get_queryset(self, request):
        return super().get_queryset(request)

    def delete_docker(self, request, queryset):
        if len(queryset) > 1:
            msg = "Only one docker can be deleted at a time."
            return self.message_user(request, msg, level=messages.ERROR)

        container_id = queryset.values_list("container_id", flat=True).first()
        client = docker.from_env()
        container_name = f"container-{container_id}"
        container = client.containers.get(container_name)
        container.stop()
        container.remove()

        return self.message_user(request, "Done", level=messages.SUCCESS)

    delete_docker.short_description = "Delete Docker"


admin.site.register(Instance, InstanceAdmin)
