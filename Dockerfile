FROM python:3.9
ENV PYTHONUNBUFFERED 1
RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code/

RUN apt-get update && apt-get install -y \
    cron \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common

# Add Docker's official GPG key
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -

# Set up Docker stable repository
RUN echo "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list

# Install Docker
RUN apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io

# Verify Docker installation
RUN docker --version

# Install fonts
RUN apt-get update && \
    apt-get install -y fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

# Rebuild the font cache
RUN fc-cache -f -v

# Later versions of pip are incompatible with the pinned version of celery.
# We should upgrade everything at some point.
RUN pip install pip==22.0.2
RUN pip install -r requirements.txt
COPY . /code/

# Expose the Django port
EXPOSE 8000
 
# Run Django’s development server
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "traders_impulse.wsgi:application"]