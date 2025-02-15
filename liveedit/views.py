from django import forms
from django.contrib.auth.decorators import permission_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.forms.utils import ErrorList
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

import wagtail
if wagtail.VERSION < (3,):
    from wagtail.core.blocks import BlockWidget
    from wagtail.core.models import Page
    from wagtail.core.blocks.stream_block import StreamValue
else:
    from wagtail.blocks import BlockWidget
    from wagtail.models import Page
    from wagtail.blocks.stream_block import StreamValue

from collections.abc import Sequence
import json
import re
from urllib.parse import urlencode, urlparse

def islist(v):
    return isinstance(v, Sequence)

def isdict(v):
    return isinstance(v, dict)

def _find_block(stream_value, raw_data, block_id):
    for i in range(len(raw_data)):
        # have we found the block we're looking for?
        if raw_data[i]['id']==block_id:
            def set_value(val):
                stream_value[i].value = val
            return stream_value[i].block, stream_value[i].value, set_value, stream_value

        # is this a streamblock/listblock?
        if islist(raw_data[i]['value']) and len(raw_data[i]['value']) and hasattr(raw_data[i]['value'][0], 'get') and raw_data[i]['value'][0].get('id'):
            # stream_value[i] may be a StreamValue or a StreamValue.StreamChild
            value = stream_value[i].value if isinstance(stream_value[i], StreamValue.StreamChild) else stream_value[i]
            rb, rv, rsv, rp = _find_block(value, raw_data[i]['value'], block_id)
            if rb:
                return rb, rv, rsv, rp

        #check structblock field values for any potential block lists
        if isdict(raw_data[i]['value']):
            for k, v in raw_data[i]['value'].items():
                if islist(v) and len(v) and hasattr(v[0], 'get') and v[0].get('id'):
                    rb, rv, rsv, rp = _find_block(stream_value[i].value[k], v, block_id)
                    if rb:
                        return rb, rv, rsv, rp

    return None, None, None, None

def find_block(stream_value, block_id):
    """
    Search through the stream_value to find the block with the given id.

    Recurses into StreamBlock and ListBlock items, and also into StructBlock
    fields.

    Returns a tuple of (Block, StreamValue.StreamChild, setter function to
    update value, parent StreamValue)

    """

    rb, rv, rsv, rp = _find_block(stream_value, stream_value.raw_data, block_id)
    if rb is None:
        raise Exception("Couldn't find block %s in %s"%(block_id, stream_value))
        
    return rb, rv, rsv, rp

def modify_block(action, blocks, block_id):
    for i in range(len(blocks)):
        if action=="move_up" and i>0 and blocks[i]['id']==block_id:
            #swap with previous
            blocks[i-1], blocks[i] = blocks[i], blocks[i-1]
            return True #did the move
        elif action=="move_down" and i<(len(blocks)-1) and blocks[i]['id']==block_id:
            #swap with next
            blocks[i+1], blocks[i] = blocks[i], blocks[i+1]
            return True #did the move

        #is this a list?
        if islist(blocks[i]['value']):
            for v in blocks[i]['value']:
                if islist(v) and len(v) and hasattr(v[0], 'get') and v[0].get('id'):
                    if modify_block(action, v, block_id):
                        #if block was moved, stop looking
                        return True

        #search through all fields for any potential block lists
        if isdict(blocks[i]['value']):
            for v in blocks[i]['value'].values():
                if islist(v) and len(v) and hasattr(v[0], 'get') and v[0].get('id'):
                    if modify_block(action, v, block_id):
                        #if block was moved, stop looking
                        return True

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
        elif not obj.get_latest_revision() or obj.get_latest_revision().user != request.user or (timezone.now() - obj.get_latest_revision().created_at).total_seconds() >= 3600:
            # Create and publish a new revision
            def save():
                obj.save_revision(user=request.user).publish(user=request.user)
    return obj, save

def check_can_edit(user, obj, field_name):
    if hasattr(obj, 'permissions_for_user'):
        if not obj.permissions_for_user(user).can_edit():
            raise PermissionDenied
    elif not user.has_perm("%s.change" % obj._meta.app_label):
        raise PermissionDenied

    # For pages and snippets, check the requested field is present on the normal edit panel.

    if isinstance(obj, Page):
        if field_name not in obj.get_edit_handler().get_form_options()['fields']:
            raise PermissionDenied
    elif hasattr(obj, 'snippet_viewset'):
        if field_name not in obj.snippet_viewset.get_edit_handler().get_form_options()['fields']:
            raise PermissionDenied

def render_edit_panel(request, d):
    # Steal all of the <script> and stylesheet tags from the admin base template
    admin_base = render_to_string("wagtailadmin/admin_base.html", request=request)
    script_tags = mark_safe("\n".join(re.findall('<script[^>]*>.*?</script>', admin_base, re.DOTALL)))
    stylesheet_tags = mark_safe("\n".join(re.findall('<link rel="stylesheet"[^>]+/?>', admin_base, re.DOTALL)))

    editor_css = ""
    if wagtail.VERSION < (4,):
        editor_css = mark_safe(render_to_string("wagtailadmin/pages/_editor_css.html", request=request))

    ret = render(request, "liveedit/edit_panel.html", {
        **d,
        'script_tags': script_tags,
        'stylesheet_tags': stylesheet_tags,
        'editor_css': editor_css
    })
    ret['X-Frame-Options'] = 'SAMEORIGIN'
    return ret

def ReloadResponse(jump_to_id=None):
    msg = {'action':"reload", 'jump_to_id':jump_to_id}
    ret = HttpResponse('''
    <script>window.parent.postMessage(''' + json.dumps(msg) + ''', '*');</script>
    ''')
    ret['X-Frame-Options'] = 'SAMEORIGIN'
    return ret

# wrapper to workaround Wagtail's assumption that all blocks have a top level StreamBlock
class ErrorWrapper:
    def __init__(self, err):
        self.err = err
    def as_data(self):
        if wagtail.VERSION < (5,):
            return self.err
        return [self.err]

def wrap_error(err):
    if wagtail.VERSION < (5,):
        return ErrorWrapper(err)

    if err is None:
        return None

    return ErrorWrapper(err)

@csrf_exempt
@require_http_methods(["POST"])
@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def action_view(request):
    ct = get_object_or_404(ContentType.objects, pk=request.POST['content_type_id'])
    obj = get_object_or_404(ct.model_class().objects, pk=request.POST['object_id'])
    check_can_edit(request.user, obj, request.POST['object_field'])
    obj, save = get_latest_revision_and_save_function(obj, request)
    value = getattr(obj, request.POST['object_field'], None)
    assert isinstance(value, StreamValue), "Expected a StreamValue, got %r" % value

    block_id = request.POST['id']

    modify_block(request.POST['action'], value.raw_data, block_id)
    save()

    return HttpResponseRedirect(request.POST['redirect_url'])

@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def edit_block_view(request):
    from wagtail.admin.views.pages.edit import EditView
    view = EditView.as_view()

    ct = get_object_or_404(ContentType.objects, pk=request.GET['content_type_id'])
    obj = get_object_or_404(ct.model_class().objects, pk=request.GET['object_id'])
    check_can_edit(request.user, obj, request.GET['object_field'])
    obj, save = get_latest_revision_and_save_function(obj, request)
    value = getattr(obj, request.GET['object_field'], None)
    assert isinstance(value, StreamValue), "Expected a StreamValue, got %r" % value

    block_id = request.GET['id']
    block, block_value, set_value, parent = find_block(value, block_id)

    errors = wrap_error(None)
    if request.method=="POST" and request.POST.get('delete'):
        for i, block in enumerate(parent):
            if block.id==block_id:
                del parent[i]
                save()
                return ReloadResponse()

    elif request.method=="POST":
        val = block.value_from_datadict(request.POST, request.FILES, 'block_edit_form')
        try:
            val = block.clean(val)

            set_value(val)
            save()

            return ReloadResponse(block_id)

        except forms.ValidationError as e:
            errors = wrap_error(e)
            block_value = val

    bw = BlockWidget(block)

    return render_edit_panel(request, {
        'form_html': bw.render_with_errors('block_edit_form', block_value, errors=errors),
        'form_media': bw.media,
    })

@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def append_block_view(request):
    ct = get_object_or_404(ContentType.objects, pk=request.GET['content_type_id'])
    obj = get_object_or_404(ct.model_class().objects, pk=request.GET['object_id'])
    check_can_edit(request.user, obj, request.GET["object_field"])
    obj, save = get_latest_revision_and_save_function(obj, request)
    value = getattr(obj, request.GET['object_field'], None)
    assert isinstance(value, StreamValue), "Expected a StreamValue, got %r" % value

    block_id = request.GET.get('id')
    if not block_id:
        # No existing block, use the top-level StreamValue as the parent.
        parent_value = value
    else:
        # Find the block within the StreamValue and use its parent.
        _, _, _, parent_value = find_block(value, block_id)

    parent_block = parent_value.stream_block
    blank_value = StreamValue(parent_value.stream_block, [])

    errors = wrap_error(None)
    if request.method=="POST":
        val = parent_block.value_from_datadict(request.POST, request.FILES, 'block_edit_form')
        try:
            val = parent_block.clean(val)

            # Default to inserting the new block(s) at the top
            insert_index = 0
            for i, v in enumerate(parent_value):
                if block_id and v.id==block_id:
                    # Insert after this block
                    insert_index = i+1
                    break

            # Insert the new block(s) into the parent
            for j, added in enumerate(val):
                parent_value.insert(insert_index+j, added)

                # The above insert call leaves the _raw_data entry as None,
                # which will cause search indexing to error - Wagtail probably
                # isn't expecting us to meddle with StreamValues like this.
                #
                # Thus we also need to populate the _raw_data entry manually.

                parent_value._raw_data[insert_index+j] = added.get_prep_value()

            save()

            return ReloadResponse()
        except forms.ValidationError as e:
            errors = wrap_error(e)
            blank_value = val

    bw = BlockWidget(parent_block)

    return render_edit_panel(request, {
        'form_html': bw.render_with_errors('block_edit_form', blank_value, errors=errors),
        'form_media': bw.media,
    })
