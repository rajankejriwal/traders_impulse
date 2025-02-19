# Use a base image, e.g., an official Ubuntu image
FROM ubuntu:20.04

FROM python:3.9
ENV PYTHONUNBUFFERED 1

# Set environment variable to avoid some interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code/

# Install Docker dependencies and Docker itself
RUN apt-get update && \
    apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release && \
    mkdir -m 0755 -p /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | tee /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu focal stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce docker-ce-cli containerd.io && \
    rm -rf /var/lib/apt/lists/*

# Later versions of pip are incompatible with the pinned version of celery.
# We should upgrade everything at some point.
RUN pip install pip==22.0.2
RUN pip install -r requirements.txt
COPY . /code/

# Expose the Django port
EXPOSE 8000
 
# Run Django’s development server
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "traders_impulse.wsgi:application"]