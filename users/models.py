from django.contrib.auth.models import User
from django.db import models


class UserConfig(models.Model):
    """Class to store the user configurations."""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    server_id = models.CharField(max_length=1024)
