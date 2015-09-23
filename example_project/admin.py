from __future__ import unicode_literals

from django.contrib import admin
from example_project import models

import bulk_admin


class ProjectInline(bulk_admin.StackedBulkInlineModelAdmin):
    model = models.Project
    raw_id_fields = ('images',)


@admin.register(models.Image)
class ImageAdmin(bulk_admin.BulkModelAdmin):
    search_fields = ('title',)


@admin.register(models.Project)
class ProjectAdmin(bulk_admin.BulkModelAdmin):
    raw_id_fields = ('images',)
    bulk_inline = ProjectInline
