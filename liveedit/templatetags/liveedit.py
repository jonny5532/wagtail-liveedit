from django import template
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html
from django.utils.module_loading import import_string

from wagtail.admin.views.pages.preview import PreviewOnEdit

try:
    # Wagtail >= 5.0
    from wagtail.models import Page
except:
    from wagtail.core.models import Page

try:
    # Wagtail >= 4.0
    from wagtail.models import Revision as PageRevision
except:
    from wagtail.core.models import PageRevision

import json

if hasattr(PageRevision, "as_object"):
    # Wagtail >= 5.0

    # monkey-patch PageRevision.as_object to store revision id on pages
    original_as_object = PageRevision.as_object
    def as_object(self, *args, **kwargs):
        page = original_as_object(self, *args, **kwargs)
        page._live_edit_revision_id = self.id
        return page
    PageRevision.as_object = as_object

else:
    # monkey-patch PageRevision.as_page_object to store revision id on pages
    original_as_page_object = PageRevision.as_page_object
    def as_page_object(self, *args, **kwargs):
        page = original_as_page_object(self, *args, **kwargs)
        page._live_edit_revision_id = self.id
        return page
    PageRevision.as_page_object = as_page_object

if hasattr(PreviewOnEdit, 'get_object'): 
    # Wagtail >= 4.0

    # monkey-patch PreviewOnEdit.get_object so we can tell if we're looking at a unsaved preview
    original_get_object = PreviewOnEdit.get_object
    def get_object(self, *args, **kwargs):
        page = original_get_object(self, *args, **kwargs)
        page._live_edit_is_preview = True
        return page
    PreviewOnEdit.get_object = get_object
else:
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

def _is_editing_allowed(object, request):
    if isinstance(object, Page):
        perms = object.permissions_for_user(request.user)
        if not perms.can_edit():
            return False, None

        if object.has_unpublished_changes:
            # There is a new unpublished version of this page, are we looking at it?
            cur_rev_id = getattr(object, '_live_edit_revision_id', None)
            latest_rev_id = object.get_latest_revision().id

            if cur_rev_id!=latest_rev_id:
                # We're not, so don't allow live editing, but send a link to the latest revision.
                return False, format_html("<script>window._live_edit_draft_url='{}';</script>",
                    reverse('wagtailadmin_pages:revisions_view', args=(object.id, latest_rev_id))
                )

            if getattr(object, '_live_edit_is_preview', False):
                # We're viewing an unsaved preview, don't allow editing
                return False, None

        elif getattr(request, 'is_dummy', False):
            # We are in preview mode, without a unpublished revision, don't allow editing
            return False, None

    elif not request.user.has_perm("%s.change" % object._meta.app_label):
        return False, None
    
    return True, None

@register.simple_tag(takes_context=True)
def liveedit_attributes(context, block=None, object=None, field=None):
    """
    Output the HTML attributes to enable a block to be live edited.

    Ordinarily, the `block`, `object` and `field` arguments are not necessary
    since they'll have been provided by the `liveedit_include_block` invocation.
    However, if you want to include the live editing attributes manually, you
    can pass them as arguments to this tag.
    """

    data = {
        **(context.get('liveedit_data') or {})
    }

    if block and object and field:
        request = context.get('request')
        if not request:
            return ''
        
        editing_allowed, _ = _is_editing_allowed(object, request)
        if not editing_allowed:
            return ''

        data.update({
            'id': block.id,
            'block_type': block.block_type,
            'content_type_id': ContentType.objects.get_for_model(object).id,
            'object_id': object.id,
            'object_field': field
        })

    if not data.get('id'):
        return ''

    return format_html('data-liveedit="{}"', 
        json.dumps(data)
    )

@register.simple_tag(takes_context=True)
def liveedit_include_block(context, block, object=None, field=None):
    """
    Includes a StreamField block in the page, just like Wagtail's
    `include_block`, but adds live editing capabilities.

    The `object` argument is the object (eg, the page) that the StreamField that
    this block came from is on.

    The `field` argument is the name of the StreamField on that object, eg 'body'.
    """

    context = context.flatten()
    request = context.get('request')

    def finish():
        if not block:
            return ''
        return block.render_as_block(context)

    if not is_enabled(request) or not is_authenticated(request):
        return finish()

    data = {
        **(context.get('liveedit_data') or {}), 
        **({
            'id':block.id,
            'block_type': block.block_type
        } if block else {})
    }

    if object and field:
        editing_allowed, extra = _is_editing_allowed(object, request)
        if not editing_allowed:
            if extra:
                return finish() + extra
            return finish()

        data.update({
            'content_type_id': ContentType.objects.get_for_model(object).id,
            'object_id': object.id,
            'object_field': field
        })

    context['liveedit_data'] = data

    if not block:
        # No block to render, so insert a placeholder that can be used to
        # insert a new block.
        return format_html(
            '<div data-liveedit="{}" style="height: 2px"></div>',
            json.dumps(context['liveedit_data'])
        )
    
    return finish()

@register.simple_tag(takes_context=True)
def liveedit_insert_new(context, object, field):
    """
    Insert a placeholder which allows the user to insert a new block into a
    StreamField. This is useful if a StreamField has no blocks in yet, to allow
    the user to add one.
    """
    
    return liveedit_include_block(context, None, object, field)
