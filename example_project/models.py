from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class Image(models.Model):
    title = models.CharField(max_length=255, unique=True)
    data = models.FileField(null=True, blank=True)

    def __str__(self):
        return self.title


@python_2_unicode_compatible
class Project(models.Model):
    title = models.CharField(max_length=255, unique=True)
    images = models.ManyToManyField(Image, blank=True)

    def __str__(self):
        return self.title
