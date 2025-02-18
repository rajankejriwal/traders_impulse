import docker
import sys

args = sys.argv[1]

# Initialize the Docker client
client = docker.from_env()

# Specify the existing image you want to extend
existing_image = "python:3.9"  # You can change this to your base image

# Specify the name for the new image
new_image_name = args

# Dockerfile contents for extending the base image
dockerfile = """
FROM python:3.9

RUN apt-get update && apt-get install -y curl

WORKDIR /app
COPY utils/. /app

CMD ["python", "app.py"]
"""

# Write the Dockerfile to a temporary file (for the build process)
dockerfile_name = f"Dockerfile-{new_image_name}"
dockerfile_path = f"/tmp/{dockerfile_name}"
with open(dockerfile_path, "w") as f:
    f.write(dockerfile)

# Build the new image from the Dockerfile
try:
    print("Building the new image...")
    image, build_logs = client.images.build(
        path=".", dockerfile=dockerfile_path, tag=new_image_name
    )

    # Print build logs
    for log in build_logs:
        print(log.get("stream", ""))

except Exception as e:
    print(f"Error building image: {e}")

# Run a container from the new image
# try:
#     print("Running the container from the new image...")
#     container_name = f"container-{new_image_name}"
#     container = client.containers.run(new_image_name, detach=True, name=container_name)

#     # Output the container details
#     print(f"Container started with ID: {container.id}")
# except Exception as e:
#     print(f"Error running container: {e}")
