from django import template
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html
from django.utils.module_loading import import_string

from wagtail.admin.views.pages.preview import PreviewOnEdit
from wagtail.core.models import Page, PageRevision

import json

# monkey-patch PageRevision.as_page_object to store revision id on pages
original_as_page_object = PageRevision.as_page_object
def as_page_object(self, *args, **kwargs):
    page = original_as_page_object(self, *args, **kwargs)
    page._live_edit_revision_id = self.id
    return page
PageRevision.as_page_object = as_page_object

# monkey-patch PreviewOnEdit.get_page so we can tell if we're looking at a unsaved preview
original_get_page = PreviewOnEdit.get_page
def get_page(self, *args, **kwargs):
    page = original_get_page(self, *args, **kwargs)
    page._live_edit_is_preview = True
    return page
PreviewOnEdit.get_page = get_page

register = template.Library()

is_enabled = import_string(getattr(settings, 'LIVEEDIT_ENABLED_CHECK', 'liveedit.utils.is_enabled'))

def is_authenticated(request):
    if request and request.user and request.user.is_authenticated:
        return True
    return False

@register.simple_tag(takes_context=True)
def liveedit_css(context):
    request = context.get('request')
    if not is_enabled(request) or not is_authenticated(request):
        return ''
    return format_html(
        '<link rel="stylesheet" type="text/css" href="{}">',
        static('css/liveedit.css')
    )

@register.simple_tag(takes_context=True)
def liveedit_js(context):
    request = context.get('request')
    if not is_enabled(request) or not is_authenticated(request):
        return ''
    return format_html(
        '<script type="text/javascript" src="{}"></script>',
        static('js/liveedit.js')
    )

@register.simple_tag(takes_context=True)
def liveedit_attributes(context):
    if 'liveedit_data' not in context:
        return ''

    return format_html('data-liveedit="{}"', 
        json.dumps(context['liveedit_data'])
    )

@register.simple_tag(takes_context=True)
def liveedit_include_block(context, block, object=None, field=None):
    context = context.flatten()
    request = context.get('request')

    def finish():
        return block.render_as_block(context)

    if not is_enabled(request) or not is_authenticated(request):
        return finish()

    if object and isinstance(object, Page):
        perms = object.permissions_for_user(request.user)
        if not perms.can_edit():
            return finish()

    data = {
        **(context.get('liveedit_data') or {}), 
        'id':block.id,
        'block_type': block.block_type
    }

    if object and field:
        if isinstance(object, Page):
            if object.has_unpublished_changes:
                # There is a new unpublished version of this page, are we looking at it?
                cur_rev_id = getattr(object, '_live_edit_revision_id', None)
                latest_rev_id = object.get_latest_revision().id

                if cur_rev_id!=latest_rev_id:
                    # We're not, so don't allow live editing, but send a link to the latest revision.
                    return finish() + format_html("<script>window._live_edit_draft_url='{}';</script>",
                            reverse('wagtailadmin_pages:revisions_view', args=(object.id, latest_rev_id))
                        )

                if getattr(object, '_live_edit_is_preview', False):
                    # We're viewing an unsaved preview, don't allow editing
                    return finish()

            elif getattr(request, 'is_dummy', False):
                # We are in preview mode, without a unpublished revision, don't allow editing
                return finish()

        data.update({
            'content_type_id': ContentType.objects.get_for_model(object).id,
            'object_id': object.id,
            'object_field': field
        })

    context['liveedit_data'] = data
    
    return finish()
