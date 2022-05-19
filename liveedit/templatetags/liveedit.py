from django import template
from django.contrib.contenttypes.models import ContentType
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html

from wagtail.core.models import Page, PageRevision

import json


# monkey-patch PageRevision.as_page_object to store revision id on pages
original_as_page_object = PageRevision.as_page_object
def as_page_object(self):
    page = original_as_page_object(self)
    page._live_edit_revision_id = self.id
    return page
PageRevision.as_page_object = as_page_object


register = template.Library()

@register.simple_tag(takes_context=True)
def liveedit_css(context):
    request = context.get('request')
    if not request or not request.user or not request.user.is_authenticated: 
        return ''
    return format_html(
        '<link rel="stylesheet" type="text/css" href="{}">',
        static('css/liveedit.css')
    )

@register.simple_tag(takes_context=True)
def liveedit_js(context):
    request = context.get('request')
    if not request or not request.user or not request.user.is_authenticated: 
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

    if not request or not request.user or not request.user.is_authenticated: 
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
                # There is a unpublished version of this page, are we looking at it?
                cur_rev_id = getattr(object, '_live_edit_revision_id', None)
                latest_rev_id = object.get_latest_revision().id

                if cur_rev_id!=latest_rev_id:
                    # We're not, so don't allow live editing, but send a link to the latest revision.
                    return finish() + format_html("<script>window._live_edit_draft_url='{}';</script>",
                            reverse('wagtailadmin_pages:revisions_view', args=(object.id, latest_rev_id))
                        )

                live_edit_json = getattr(object, '_live_edit_json', None)
                if live_edit_json is None:
                    live_edit_json = object.get_latest_revision().content_json

                # Has page content been tampered with since it was loaded? (eg, by a unsaved preview?)
                if live_edit_json and live_edit_json!=object.to_json():
                    # Yes, so don't allow editing
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
