from __future__ import unicode_literals

from django.test import TestCase
from django.contrib.admin.sites import site as admin_site
from django.contrib.auth.models import Permission, User
from django.urls import reverse
from django.utils import six
from io import BytesIO

from bulk_admin.admin import BulkInlineModelAdmin
from example_project.models import Image, Project

import sys


class BulkTests(TestCase):

    def setUp(self):
        self.bulk_url = reverse('admin:{}_{}_bulk'.format(Image._meta.app_label, Image._meta.model_name))
        self.changelist_url = reverse('admin:{}_{}_changelist'.format(Image._meta.app_label, Image._meta.model_name))
        self.add_url = reverse('admin:{}_{}_add'.format(Image._meta.app_label, Image._meta.model_name))
        self.index_url = reverse('admin:index')

        self.add_permission = Permission.objects.get(codename='add_{}'.format(Image._meta.model_name))
        self.change_permission = Permission.objects.get(codename='change_{}'.format(Image._meta.model_name))
        self.delete_permission = Permission.objects.get(codename='delete_{}'.format(Image._meta.model_name))

        self.user = User.objects.create_user('grill', 'ruben@grill.de', 'grill')
        self.user.user_permissions.add(self.add_permission)
        self.user.user_permissions.add(self.change_permission)
        self.user.user_permissions.add(self.delete_permission)
        self.user.is_staff = True
        self.user.save()

        self.user_not_staff = User.objects.create_user('not_staff', 'not@staff.de', 'not_staff')

        self.client.login(username='grill', password='grill')

    def bulk_payload(self, objects, **extra):
        changed_objects = [obj for obj in objects if 'id' in obj]
        new_objects = [obj for obj in objects if 'id' not in obj]
        payload = {
            'form-TOTAL_FORMS': len(objects),
            'form-INITIAL_FORMS': len(changed_objects),
        }

        for index, obj in enumerate(changed_objects):
            for name, value in six.iteritems(obj):
                payload['form-{index}-{name}'.format(index=index, name=name)] = value

        for index, obj in enumerate(new_objects, len(changed_objects)):
            for name, value in six.iteritems(obj):
                payload['form-{index}-{name}'.format(index=index, name=name)] = value

        payload.update(extra)

        return payload

    def bulk_upload_payload(self, field, files, **extra):
        payload = {
            'form-TOTAL_FORMS': len(files),
            'form-INITIAL_FORMS': 0,
            'form-{}'.format(field): files,
        }

        payload.update(extra)

        return payload

    def assertRedirects(self, response, expected_url):
        # Don't fetch redirect response in python 3.2, as sessionid cookie gets lost due to a bug in cookie parsing.
        # Happens when messages are used and messages cookie comes before sessionid cookie and contains square brackets.
        # See https://bugs.python.org/issue22931
        fetch_redirect_response = False if sys.version_info >= (3, 2) and sys.version_info < (3, 3) else True
        super(BulkTests, self).assertRedirects(response, expected_url, fetch_redirect_response=fetch_redirect_response)

    def assertImagesEqual(self, qs, images, ordered=True, msg=None):
        def transform_to_dict(obj):
            return {field.name: getattr(obj, field.name) for field in obj._meta.fields if getattr(obj, field.name)}

        values = []

        for image in images:
            if isinstance(image, Image):
                values.append(transform_to_dict(image))

            else:
                image = dict(image)
                image.pop('DELETE', None)
                try:
                    image['id'] = getattr(image, 'id', None) or Image.objects.get(title=image['title']).id
                except Image.DoesNotExist:
                    pass
                values.append(image)

        return super(BulkTests, self).assertQuerysetEqual(qs, values, transform_to_dict, ordered, msg)

    def getTestQueryset(self):
        return Image.objects.exclude(title__startswith='preexisting')

    def getResponseQueryset(self, response):
        return response.context['inline_admin_formsets'][0].formset.queryset

    def test_http_get_bulk(self):
        response = self.client.get(self.bulk_url)

        self.assertEqual(response.status_code, 200)

    def test_http_get_bulk_with_pks(self):
        Image.objects.create(title='preexisting - I might not be included in response queryset!')

        image = Image.objects.create(title='foo')

        response = self.client.get('{}?pks={}'.format(self.bulk_url, image.pk))

        self.assertEqual(response.status_code, 200)
        self.assertImagesEqual(self.getResponseQueryset(response), [image])

    def test_http_get_bulk_with_pks_without_change_permission(self):
        self.user.user_permissions.remove(self.change_permission)

        image = Image.objects.create(title='foo')

        response = self.client.get('{}?pks={}'.format(self.bulk_url, image.pk))

        self.assertEqual(response.status_code, 200)
        self.assertImagesEqual(self.getResponseQueryset(response), [])

    def test_http_get_bulk_not_staff(self):
        self.client.login(username='not_staff', password='not_staff')

        response = self.client.get(self.bulk_url)

        self.assertRedirects(response, '/admin/login/?next={}'.format(self.bulk_url))

    def test_add_image_and_save(self):
        images = [{'title': 'foo'}]
        payload = self.bulk_payload(images)
        response = self.client.post(self.bulk_url, payload)

        self.assertRedirects(response, self.changelist_url)
        self.assertImagesEqual(self.getTestQueryset(), images)

    def test_add_image_and_save_without_add_permission(self):
        self.user.user_permissions.remove(self.add_permission)

        images = [{'title': 'foo'}]
        payload = self.bulk_payload(images)
        response = self.client.post(self.bulk_url, payload)

        self.assertEqual(response.status_code, 403)
        self.assertImagesEqual(self.getTestQueryset(), [])

    def test_add_image_and_save_without_change_permission(self):
        self.user.user_permissions.remove(self.change_permission)

        images = [{'title': 'foo'}]
        payload = self.bulk_payload(images)
        response = self.client.post(self.bulk_url, payload)

        self.assertRedirects(response, self.index_url)
        self.assertImagesEqual(self.getTestQueryset(), images)

    def test_add_image_and_continue(self):
        Image.objects.create(title='preexisting - I might not be included in response queryset!')

        images = [{'title': 'foo'}]
        payload = self.bulk_payload(images, _continue=1)
        response = self.client.post(self.bulk_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertImagesEqual(self.getTestQueryset(), images)
        self.assertImagesEqual(self.getResponseQueryset(response), images)

    def test_add_image_and_continue_without_change_permission(self):
        Image.objects.create(title='preexisting - I might not be included in response queryset!')

        self.user.user_permissions.remove(self.change_permission)

        images = [{'title': 'foo'}]
        payload = self.bulk_payload(images, _continue=1)
        response = self.client.post(self.bulk_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertImagesEqual(self.getTestQueryset(), images)
        self.assertImagesEqual(self.getResponseQueryset(response), [])

    def test_add_image_and_add_another(self):
        images = [{'title': 'foo'}]
        payload = self.bulk_payload(images, _addanother=1)
        response = self.client.post(self.bulk_url, payload)

        self.assertRedirects(response, self.add_url)
        self.assertImagesEqual(self.getTestQueryset(), images)

    def test_change_image_and_save(self):
        image = Image.objects.create(title='foo')
        images = [{'title': 'bar', 'id': image.id}]
        payload = self.bulk_payload(images)
        response = self.client.post(self.bulk_url, payload)

        self.assertRedirects(response, self.changelist_url)
        self.assertImagesEqual(self.getTestQueryset(), images)

    def test_change_image_and_save_without_change_permission(self):
        self.user.user_permissions.remove(self.change_permission)

        image = Image.objects.create(title='foo')
        images = [{'title': 'bar', 'id': image.id}]
        payload = self.bulk_payload(images)
        response = self.client.post(self.bulk_url, payload)

        self.assertEqual(response.status_code, 403)
        self.assertImagesEqual(self.getTestQueryset(), [image])

    def test_change_image_and_save_without_add_permission(self):
        self.user.user_permissions.remove(self.add_permission)

        self.test_change_image_and_save()

    def test_change_image_and_continue(self):
        Image.objects.create(title='preexisting - I might not be included in response queryset!')

        image = Image.objects.create(title='foo')
        images = [{'title': 'bar', 'id': image.id}]
        payload = self.bulk_payload(images, _continue=1)
        response = self.client.post(self.bulk_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertImagesEqual(self.getTestQueryset(), images)
        self.assertImagesEqual(self.getResponseQueryset(response), images)

    def test_change_image_and_add_another(self):
        image = Image.objects.create(title='foo')
        images = [{'title': 'bar', 'id': image.id}]
        payload = self.bulk_payload(images, _addanother=1)
        response = self.client.post(self.bulk_url, payload)

        self.assertRedirects(response, self.add_url)
        self.assertImagesEqual(self.getTestQueryset(), images)

    def test_delete_image_and_save(self):
        image = Image.objects.create(title='foo')
        images = [{'title': image.title, 'id': image.id, 'DELETE': True}]
        payload = self.bulk_payload(images)
        response = self.client.post(self.bulk_url, payload)

        self.assertRedirects(response, self.changelist_url)
        self.assertImagesEqual(self.getTestQueryset(), [])

    def test_delete_image_and_save_without_delete_permission(self):
        self.user.user_permissions.remove(self.delete_permission)

        image = Image.objects.create(title='foo')
        images = [{'title': image.title, 'id': image.id, 'DELETE': True}]
        payload = self.bulk_payload(images)
        response = self.client.post(self.bulk_url, payload)

        self.assertRedirects(response, self.changelist_url)
        self.assertImagesEqual(self.getTestQueryset(), images)

    def test_bulk_upload(self):
        with BytesIO(b'data1') as data1, BytesIO(b'data2') as data2:
            # Django < 1.8 requires *name* attribute
            data1.name = 'data1.txt'
            data2.name = 'data2.txt'

            payload = self.bulk_upload_payload('data', [data1, data2])
            response = self.client.post(self.bulk_url, payload)
            images = list(Image.objects.all())

            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(images), 2)

            for image, data in zip(images, [data1, data2]):
                with image.data as image_data:
                    self.assertEqual(image_data.read(), data.getvalue())

    def test_bulk_inline_model_admin_without_model(self):
        class ImageInline(BulkInlineModelAdmin):
            pass

        ImageInline(Image, admin_site)

    def test_bulk_inline_model_admin_with_same_model(self):
        class ImageInline(BulkInlineModelAdmin):
            model = Image

        ImageInline(Image, admin_site)

    def test_bulk_inline_model_admin_with_different_model(self):
        class ImageInline(BulkInlineModelAdmin):
            model = Project

        error = (
            'ImageInline with model Project may only be used as bulk_inline '
            'within a ModelAdmin having the same model, '
            'but was used inside a ModelAdmin with model Image'
        )

        with self.assertRaisesRegexp(Exception, error):
            ImageInline(Image, admin_site)
