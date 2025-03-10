from django.db import models


class Instance(models.Model):
    first_name = models.CharField(max_length=1024)
    last_name = models.CharField(max_length=1024)
    account_number = models.CharField(max_length=1024, null=True, blank=True)
    container_id = models.CharField(max_length=1024)
    logs = models.CharField(max_length=1024)

    def __str__(self):
        return self.first_name
