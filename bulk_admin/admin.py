from __future__ import unicode_literals

from collections import OrderedDict
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.exceptions import DisallowedModelAdminToField
from django.contrib.admin.options import IS_POPUP_VAR, InlineModelAdmin, TO_FIELD_VAR, csrf_protect_m
from django.contrib.admin.templatetags.admin_static import static
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.contrib.admin.utils import NestedObjects, flatten_fieldsets
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.db import router, transaction
from django.forms.formsets import DELETION_FIELD_NAME, INITIAL_FORM_COUNT, TOTAL_FORM_COUNT, ManagementForm
from django.forms.models import modelform_defines_fields, modelformset_factory, BaseModelFormSet
from django.forms.utils import ErrorList
from django.http import HttpResponseRedirect
from django.template.response import SimpleTemplateResponse
from django.utils import six
from django.utils.encoding import force_text
from django.utils.text import get_text_list
from django.utils.translation import ugettext as _, ugettext_lazy
from functools import partial, update_wrapper

import django
import re
import uuid


_RE_BULK_FILE = re.compile(r'^([^\\-]+)-([^\\-]+)$')


class BulkModelAdmin(admin.ModelAdmin):

    actions = ['bulk_edit_action']
    bulk_generate_unique_values = None
    bulk_inline = None
    bulk_upload_fields = None
    change_list_template = None
    add_form_template = None
    change_form_template = None

    def __init__(self, *args, **kwargs):
        super(BulkModelAdmin, self).__init__(*args, **kwargs)

        opts = self.model._meta
        app_label = opts.app_label

        self.change_list_template = self.change_list_template or [
            'bulk_admin/%s/%s/bulk_change_list.html' % (app_label, opts.model_name),
            'bulk_admin/%s/bulk_change_list.html' % app_label,
            'bulk_admin/bulk_change_list.html'
        ]

        self.add_form_template = self.add_form_template or [
            'bulk_admin/%s/%s/bulk_change_form.html' % (app_label, opts.model_name),
            'bulk_admin/%s/bulk_change_form.html' % app_label,
            'bulk_admin/bulk_change_form.html'
        ]

        self.change_form_template = self.change_form_template or [
            'bulk_admin/%s/%s/bulk_change_form.html' % (app_label, opts.model_name),
            'bulk_admin/%s/bulk_change_form.html' % app_label,
            'bulk_admin/bulk_change_form.html'
        ]

    def get_urls(self):
        from django.conf.urls import url

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name

        urlpatterns = super(BulkModelAdmin, self).get_urls()
        urlpatterns.insert(0, url(r'^bulk/$', wrap(self.bulk_view), name='%s_%s_bulk' % info))

        return urlpatterns

    @csrf_protect_m
    @transaction.atomic
    def bulk_view(self, request, form_url='', extra_context=None):
        to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
        if to_field and not self.to_field_allowed(request, to_field):
            raise DisallowedModelAdminToField("The field %s cannot be referenced." % to_field)

        model = self.model
        opts = model._meta

        continue_requested = request.POST.get('_continue', request.GET.get('_continue'))
        force_continue = False
        inline = self.get_bulk_inline(request)
        formset_class = inline.get_formset(request)
        formset_params = {}
        prefix = formset_class.get_default_prefix()
        queryset = inline.get_queryset(request)

        if not self.has_add_permission(request):
            formset_class.max_num = 0

        if request.method == 'GET':
            if 'pks' in request.GET and self.has_change_permission(request):
                pks = [opts.pk.to_python(pk) for pk in request.GET.get('pks').split(',')]
                queryset = queryset.filter(pk__in=pks)
            else:
                queryset = queryset.none()

        elif request.method == 'POST':
            management_form = ManagementForm(request.POST, prefix=prefix)

            if not management_form.is_valid():
                raise ValidationError(
                    _('ManagementForm data is missing or has been tampered with'),
                    code='missing_management_form',
                )

            if not self.has_add_permission(request) and management_form.cleaned_data[INITIAL_FORM_COUNT] < management_form.cleaned_data[TOTAL_FORM_COUNT]:
                raise PermissionDenied

            if not self.has_change_permission(request) and management_form.cleaned_data[INITIAL_FORM_COUNT] > 0:
                raise PermissionDenied

            queryset = self.transform_queryset(request, queryset, management_form, prefix)

            post, files, force_continue = self.transform_post_and_files(request, prefix)
            formset_params.update({
                'data': post,
                'files': files,
            })

        formset_params['queryset'] = queryset

        formset = formset_class(**formset_params)

        if request.method == 'POST':
            if formset.is_valid():
                self.save_formset(request, form=None, formset=formset, change=False)

                if continue_requested or force_continue:
                    # The implementation of ModelAdmin redirects to the change view if valid and continue was requested
                    # The change view then reads the edited model again from database
                    # In our case, we can't make a redirect as we would loose the information which models should be edited
                    # Thus, we create a new formset with the edited models and continue as this would have been a usual GET request

                    if self.has_change_permission(request):
                        queryset = _ListQueryset(queryset)
                        queryset.extend(formset.new_objects)
                    else:
                        queryset = _ListQueryset()

                    formset_params.update({
                        'data': None,
                        'files': None,
                        'queryset': queryset,
                    })

                    formset = formset_class(**formset_params)

                    msg = _('The %s were bulk added successfully. You may edit them again below.') % (force_text(opts.verbose_name_plural),)
                    self.message_user(request, msg, messages.SUCCESS)

                else:
                    return self.response_bulk(request, formset)

        media = self.media

        inline_formsets = self.get_inline_formsets(request, [formset], [inline], obj=None)
        for inline_formset in inline_formsets:
            media = media + inline_formset.media

        errors = ErrorList()

        if formset.is_bound:
            errors.extend(formset.non_form_errors())
            for formset_errors in formset.errors:
                errors.extend(list(six.itervalues(formset_errors)))

        context = dict(
            self.admin_site.each_context(request) if django.VERSION >= (1, 8) else self.admin_site.each_context(),
            bulk=True,
            bulk_formset_prefix=prefix,
            bulk_upload_fields=self.get_bulk_upload_fields(request),
            title=_('Bulk add %s') % force_text(opts.verbose_name_plural),
            is_popup=(IS_POPUP_VAR in request.POST or
                      IS_POPUP_VAR in request.GET),
            to_field=to_field,
            media=media,
            inline_admin_formsets=inline_formsets,
            errors=errors,
            preserved_filters=self.get_preserved_filters(request),
        )

        context.update(extra_context or {})

        return self.render_change_form(request, context, add=True, change=False, obj=None, form_url=form_url)

    def response_bulk(self, request, formset):
        model = self.model
        opts = model._meta
        preserved_filters = self.get_preserved_filters(request)
        msg_dict = {
            'name': force_text(opts.verbose_name),
            'name_plural': force_text(opts.verbose_name_plural),
        }

        if IS_POPUP_VAR in request.POST:
            return self.response_bulk_popup(request, list(formset.queryset) + formset.new_objects)

        elif '_addanother' in request.POST:
            msg = _('The %(name_plural)s were bulk added successfully. You may add another %(name)s below.') % msg_dict
            self.message_user(request, msg, messages.SUCCESS)
            redirect_url = reverse('admin:%s_%s_add' % (opts.app_label, opts.model_name), current_app=self.admin_site.name)
            redirect_url = add_preserved_filters({'preserved_filters': preserved_filters, 'opts': opts}, redirect_url)
            return HttpResponseRedirect(redirect_url)

        else:
            msg = _('The %(name_plural)s were bulk added successfully.') % msg_dict
            self.message_user(request, msg, messages.SUCCESS)

            return self.response_post_save_add(request, obj=None)

    def response_bulk_popup(self, request, objects):
        model = self.model
        opts = model._meta

        to_field = request.POST.get(TO_FIELD_VAR)
        if to_field:
            attr = str(to_field)
        else:
            attr = opts.pk.attname
        values = [obj.serializable_value(attr) for obj in objects]
        media = forms.Media(js=[static('bulk_admin/js/bulk-related.js')])
        return SimpleTemplateResponse('bulk_admin/bulk_popup_response.html', {
            'values': values,
            'objects': objects,
            'media': media,
        })

    def transform_queryset(self, request, queryset, management_form, prefix):
        pk_list = []
        pk_name = self.model._meta.pk.name
        pk_field = self.model._meta.pk
        to_python = pk_field.to_python

        for index in range(management_form.cleaned_data[INITIAL_FORM_COUNT]):
            pk_key = '{}-{}-{}'.format(prefix, index, pk_name)
            pk = request.POST[pk_key]
            pk = to_python(pk)
            pk_list.append(pk)

        return queryset.filter(pk__in=pk_list)

    def transform_post_and_files(self, request, prefix):
        post = request.POST.copy()
        files = request.FILES
        force_continue = False

        for field_name_prefixed, field_files in list(files.lists()):
            match = _RE_BULK_FILE.match(field_name_prefixed)

            if match and match.group(1) == prefix:
                field_name = match.group(2)

                for index, field_file in enumerate(field_files):
                    files['{}-{}-{}'.format(prefix, index, field_name)] = field_file

                    form_data_for_file = self.generate_data_for_file(request, field_name, field_file, index)

                    if form_data_for_file:
                        force_continue = True
                        post.update({
                            '{}-{}-{}'.format(prefix, index, name): value
                            for name, value
                            in six.iteritems(form_data_for_file)
                        })

        return post, files, force_continue

    def generate_data_for_file(self, request, field_name, field_file, index):
        return {field: uuid.uuid4() for field in self.get_bulk_generate_unique_values() or []}

    def get_bulk_generate_unique_values(self):
        if self.bulk_generate_unique_values is not None:
            return self.bulk_generate_unique_values

        fields = self.model._meta.get_fields() if django.VERSION >= (1, 8) else self.model._meta.fields

        return list(field.name for field in fields if not getattr(field, 'blank', True))

    def get_actions(self, request):
        if IS_POPUP_VAR in request.GET:
            return OrderedDict(select_related_action=self.get_action('select_related_action'))
        return super(BulkModelAdmin, self).get_actions(request)

    def get_bulk_inline(self, request):
        bulk_inline = self.bulk_inline or TabularBulkInlineModelAdmin
        return bulk_inline(self.model, self.admin_site)

    def get_bulk_upload_fields(self, request):
        model = self.model
        opts = model._meta

        if self.bulk_upload_fields is not None:
            return [opts.get_field(field) for field in self.bulk_upload_fields]

        fields = opts.get_fields() if django.VERSION >= (1, 8) else opts.fields

        return [field for field in fields if hasattr(field, 'upload_to')]

    @property
    def media(self):
        media = super(BulkModelAdmin, self).media
        media.add_js([static('bulk_admin/js/bulk.js')])

        return media

    def select_related_action(self, request, queryset):
        return self.response_bulk_popup(request, queryset)

    select_related_action.short_description = ugettext_lazy('Select')

    def bulk_edit_action(self, request, queryset):
        model = self.model
        opts = model._meta

        selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        redirect_url = reverse('admin:%s_%s_bulk' % (opts.app_label, opts.model_name), current_app=self.admin_site.name)

        return HttpResponseRedirect('{}?pks={}'.format(redirect_url, ','.join(selected)))

    bulk_edit_action.short_description = ugettext_lazy('Bulk edit')


class BulkInlineModelAdmin(InlineModelAdmin):

    formset = BaseModelFormSet

    def __init__(self, parent_model, admin_site):
        self.model = self.model if self.model is not None else parent_model

        if self.model != parent_model:
            raise Exception(
                '{} with model {} may only be used as bulk_inline '
                'within a ModelAdmin having the same model, '
                'but was used inside a ModelAdmin with model {}'
                .format(self.__class__.__name__, self.model.__name__, parent_model.__name__)
            )

        super(BulkInlineModelAdmin, self).__init__(parent_model=None, admin_site=admin_site)

    def get_formset(self, request, obj=None, **kwargs):
        if 'fields' in kwargs:
            fields = kwargs.pop('fields')
        else:
            fields = flatten_fieldsets(self.get_fieldsets(request, obj))
        if self.exclude is None:
            exclude = []
        else:
            exclude = list(self.exclude)
        exclude.extend(self.get_readonly_fields(request, obj))
        if self.exclude is None and hasattr(self.form, '_meta') and self.form._meta.exclude:
            # Take the custom ModelForm's Meta.exclude into account only if the
            # InlineModelAdmin doesn't define its own.
            exclude.extend(self.form._meta.exclude)
        # If exclude is an empty list we use None, since that's the actual
        # default.
        exclude = exclude or None
        can_delete = self.can_delete and self.has_delete_permission(request, obj)
        defaults = {
            "form": self.form,
            "formset": self.formset,
            "fields": fields,
            "exclude": exclude,
            "formfield_callback": partial(self.formfield_for_dbfield, request=request),
            "extra": self.get_extra(request, obj, **kwargs),
            "min_num": self.get_min_num(request, obj, **kwargs),
            "max_num": self.get_max_num(request, obj, **kwargs),
            "can_delete": can_delete,
        }

        defaults.update(kwargs)
        base_model_form = defaults['form']

        class DeleteProtectedModelForm(base_model_form):

            def hand_clean_DELETE(self):
                """
                We don't validate the 'DELETE' field itself because on
                templates it's not rendered using the field information, but
                just using a generic "deletion_field" of the InlineModelAdmin.
                """
                if self.cleaned_data.get(DELETION_FIELD_NAME, False):
                    using = router.db_for_write(self._meta.model)
                    collector = NestedObjects(using=using)
                    if self.instance.pk is None:
                        return
                    collector.collect([self.instance])
                    if collector.protected:
                        objs = []
                        for p in collector.protected:
                            objs.append(
                                # Translators: Model verbose name and instance representation,
                                # suitable to be an item in a list.
                                _('%(class_name)s %(instance)s') % {
                                    'class_name': p._meta.verbose_name,
                                    'instance': p}
                            )
                        params = {'class_name': self._meta.model._meta.verbose_name,
                                  'instance': self.instance,
                                  'related_objects': get_text_list(objs, _('and'))}
                        msg = _("Deleting %(class_name)s %(instance)s would require "
                                "deleting the following protected related objects: "
                                "%(related_objects)s")
                        raise ValidationError(msg, code='deleting_protected', params=params)

            def is_valid(self):
                result = super(DeleteProtectedModelForm, self).is_valid()
                self.hand_clean_DELETE()
                return result

        defaults['form'] = DeleteProtectedModelForm

        if defaults['fields'] is None and not modelform_defines_fields(defaults['form']):
            defaults['fields'] = forms.ALL_FIELDS

        return modelformset_factory(self.model, **defaults)


class StackedBulkInlineModelAdmin(BulkInlineModelAdmin):
    template = 'admin/edit_inline/stacked.html'


class TabularBulkInlineModelAdmin(BulkInlineModelAdmin):
    template = 'admin/edit_inline/tabular.html'


class _ListQueryset(list):
    ordered = True
