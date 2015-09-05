=================
django-bulk-admin
=================

Django bulk admin enables you to bulk add, bulk edit, bulk upload and bulk select in django admin.

View the screenshots below to get an idea of how django bulk admin does look like.


===========
Quick start
===========

1. Install with pip::

    $ pip install django-bulk-admin

2. Add "bulk_admin" to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = (
        ...
        'bulk_admin',
    )

3. Inherit from ``bulk_admin.BulkModelAdmin`` instead of ``django.contrib.admin.ModelAdmin``::

    from django.contrib import admin
    from example_project import models

    import bulk_admin


    @admin.register(models.Image)
    class ImageAdmin(bulk_admin.BulkModelAdmin):
        search_fields = ('title',)


    @admin.register(models.Project)
    class ProjectAdmin(bulk_admin.BulkModelAdmin):
        raw_id_fields = ('images',)

4. Enjoy!


===========
Bulk Upload
===========

By default, django bulk admin provides a bulk upload button for each field type that has an ``upload_to`` attribute, like ``FileField`` or ``ImageField``.
If you want to customize the provided buttons (or disable bulk upload at all), set ``bulk_upload_fields`` in the ``BulkAdminModel``::

    @admin.register(models.Image)
    class ImageAdmin(bulk_admin.BulkModelAdmin):
        bulk_upload_fields = ()

When files are bulk uploaded, a model instance is created and saved for each file.
If there are required fields, django bulk admin tries to set unique values (uuid) which can be edited by the uploading user in the next step.
For setting custom values or to support non string fields that are required, override ``generate_data_for_file``::

    @admin.register(models.Image)
    class ImageAdmin(bulk_admin.BulkModelAdmin):

        def generate_data_for_file(self, request, field_name, field_file, index):
            if field_name == 'data':
                return dict(title=field_file.name)
            return super(ImageAdmin, self).generate_data_for_file(request, field_name, file, index)


================
Customize Inline
================

Django bulk admin provides two inlines that are similar to those provided by django admin:

- ``bulk_admin.TabularBulkInlineModelAdmin`` (which is the default)
- ``bulk_admin.StackedBulkInlineModelAdmin``

You can configure them exactly like django admin one's::

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


===========
Screenshots
===========

--------
Bulk add
--------

.. image:: https://raw.githubusercontent.com/purelabs/django-bulk-admin/master/screenshots/bulk_add_1.png
.. image:: https://raw.githubusercontent.com/purelabs/django-bulk-admin/master/screenshots/bulk_add_2.png

---------
Bulk edit
---------

.. image:: https://raw.githubusercontent.com/purelabs/django-bulk-admin/master/screenshots/bulk_edit_1.png

-----------
Bulk upload
-----------

.. image:: https://raw.githubusercontent.com/purelabs/django-bulk-admin/master/screenshots/bulk_upload_1.png
.. image:: https://raw.githubusercontent.com/purelabs/django-bulk-admin/master/screenshots/bulk_upload_2.png

-----------
Bulk select
-----------

.. image:: https://raw.githubusercontent.com/purelabs/django-bulk-admin/master/screenshots/bulk_select_1.png
.. image:: https://raw.githubusercontent.com/purelabs/django-bulk-admin/master/screenshots/bulk_select_2.png
.. image:: https://raw.githubusercontent.com/purelabs/django-bulk-admin/master/screenshots/bulk_select_3.png
