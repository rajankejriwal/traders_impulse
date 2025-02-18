import subprocess

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


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

    def get(self, request, *args, **kwargs):
        unique_id = kwargs.get("unique_id", None)

        if not unique_id:
            return Response(
                {"details": "unique id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        command = f"python utils/docker_run_container.py {unique_id}"
        subprocess.run(command, shell=True)

        return Response({"details": "Done"}, status=status.HTTP_200_OK)
