import docker
import os
import subprocess
import uuid

from django.shortcuts import render
from django.urls import reverse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from start_docker.models import Instance


class CreateImage(APIView):
    """Class used to create new docker"""

    def get(self, request, *args, **kwargs):
        img_id = kwargs.get("img_id", None)

        if not img_id:
            return Response(
                {"details": "unique id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        command = f"python utils/docker_create_image.py {img_id}"
        subprocess.run(command, shell=True)

        return Response({"details": "Done"}, status=status.HTTP_200_OK)


class RunDockerWithUniqueID(APIView):
    """class used to run the docker with the unique id"""

    def post(self, request, *args, **kwargs):
        first_name = request.data.get("first_name", None)
        last_name = request.data.get("last_name", None)
        account_number = request.data.get("account_number", None)

        if not first_name or not last_name or not account_number:
            return Response(
                {"details": "first_name, last_name and account_number are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        container_id = str(uuid.uuid4())

        url = request.build_absolute_uri(
            reverse("view_logs", kwargs={"container_id": container_id})
        )

        Instance.objects.create(
            first_name=first_name,
            last_name=last_name,
            account_number=account_number,
            container_id=container_id,
            logs=url,
        )

        command = f"python utils/docker_run_container.py {container_id}"
        subprocess.run(command, shell=True)

        return Response({"container_id": container_id}, status=status.HTTP_200_OK)


# Create a custom admin view to show logs
def view_logs(request, container_id):
    # Initialize Docker client
    client = docker.from_env()

    try:
        # Get a specific container (replace with your container's name or ID)
        container_name = f"container-{container_id}"
        container = client.containers.get(container_name)
        print("***" * 10, container.status)

        if container.status == "running":
            status = "ACTIVE"
        elif container.status == "exited":
            status = "STOPPED"
        else:
            status = container.status

        # Fetch logs
        logs = container.logs(tail=100)

        if logs:
            logs = logs.decode("utf-8").split("\n")
            return render(
                request, "admin/view_logs.html", {"logs": logs, "status": status}
            )
        else:
            return render(
                request,
                "admin/view_logs.html",
                {"logs": "No logs found", "status": status},
            )
    except Exception as e:
        msg = ["something went wrong", str(e)]
        return render(request, "admin/view_logs.html", {"logs": msg, "status": status})
