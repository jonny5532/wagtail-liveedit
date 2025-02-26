from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.utils import timezone

import wagtail
if wagtail.VERSION < (3,):
    from wagtail.core.models import Page
    from wagtail.core.blocks.stream_block import StreamValue
else:
    from wagtail.models import Page
    from wagtail.blocks.stream_block import StreamValue


class BlockAppendForm(forms.Form):
    content_type_id = forms.IntegerField()
    object_id = forms.IntegerField()
    object_field = forms.CharField()
    id = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        
        try:
            cleaned_data['content_type'] = ContentType.objects.get(pk=cleaned_data['content_type_id'])
        except ContentType.DoesNotExist:
            raise forms.ValidationError("Invalid content type")

        model_class = cleaned_data['content_type'].model_class()
        try:
            cleaned_data['object'] = model_class.objects.get(pk=cleaned_data['object_id'])
        except model_class.DoesNotExist:
            raise forms.ValidationError("Invalid object")

        try:
            check_can_edit(self.request.user, cleaned_data['object'], cleaned_data['object_field'])
        except PermissionDenied:
            raise forms.ValidationError("Permission denied")

        cleaned_data['revision'], cleaned_data['save'] = get_latest_revision_and_save_function(
            cleaned_data['object'], 
            self.request,
        )

        cleaned_data['value'] = getattr(cleaned_data['revision'], cleaned_data['object_field'], None)

        if not isinstance(cleaned_data['value'], StreamValue):
            raise forms.ValidationError("Expected a StreamValue, got %r" % cleaned_data['value'])

        return cleaned_data


class BlockEditForm(BlockAppendForm):
    # Make the `id` field required
    id = forms.CharField()


class BlockActionForm(BlockEditForm):
    action = forms.CharField()
    redirect_url = forms.CharField()


def get_latest_revision_and_save_function(obj, request):
    """
    For a given model instance, return the latest revision of that model
    instance, as well as a function which saves it, as a tuple.
    """

    # The default behaviour is to update the current live page
    def save():
        obj.last_published_at = timezone.now()
        obj.save()

    if isinstance(obj, Page):
        if obj.has_unpublished_changes:
            # Modify the latest draft, not the published one
            obj = obj.get_latest_revision_as_object()

            def save():
                # Update the existing draft revision
                rev = obj.get_latest_revision()
                rev.content = obj.serializable_data()
                rev.save()

        elif (
            not obj.get_latest_revision()
            or obj.get_latest_revision().user != request.user
            or (timezone.now() - obj.get_latest_revision().created_at).total_seconds() >= 3600
        ):
            # Create and publish a new revision
            def save():
                obj.save_revision(user=request.user).publish(user=request.user)

    return obj, save


def check_can_edit(user, obj, field_name):
    """
    Check whether the supplied user has permission to edit the specified field
    on the supplied object.
    """

    if hasattr(obj, 'permissions_for_user'):
        if not obj.permissions_for_user(user).can_edit():
            raise PermissionDenied
    elif not user.has_perm("%s.change" % obj._meta.app_label):
        raise PermissionDenied

    # For pages and snippets, check the requested field is present on the normal edit panel.
    # TODO: apply similar scrutiny to modeladmin models?

    if isinstance(obj, Page):
        if field_name not in obj.get_edit_handler().get_form_options()['fields']:
            raise PermissionDenied
    elif hasattr(obj, 'snippet_viewset'):
        if field_name not in obj.snippet_viewset.get_edit_handler().get_form_options()['fields']:
            raise PermissionDenied
