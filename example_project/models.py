from django.db import models


class Image(models.Model):
    title = models.CharField(max_length=255, unique=True)
    data = models.FileField(null=True, blank=True)

    def __unicode__(self):
        return self.title


class Project(models.Model):
    title = models.CharField(max_length=255, unique=True)
    images = models.ManyToManyField(Image, blank=True)

    def __unicode__(self):
        return self.title
