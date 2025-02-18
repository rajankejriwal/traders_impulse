import docker
import sys

image_name = "img1"
unique_id = sys.argv[1]
env = {"UNIQUE_ID": unique_id}

# Initialize the Docker client
client = docker.from_env()

# Specify the existing image you want to extend
existing_image = "python:3.9"  # You can change this to your base image

# Run a container from the new image
try:
    print("Running the container from the new image...")
    container_name = f"container-{unique_id}"
    container = client.containers.run(
        image_name, detach=True, name=container_name, environment=env
    )

    # Output the container details
    print(f"Container started with ID: {container.id}")
    print("****" * 10, container.logs().decode("utf-8"))
except Exception as e:
    print(f"Error running container: {e}")
