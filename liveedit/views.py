from django import forms
from django.contrib.auth.decorators import permission_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.forms.utils import ErrorList
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt

from wagtail.contrib.modeladmin.helpers import PermissionHelper
from wagtail.core.blocks import BlockWidget
from wagtail.core.blocks.stream_block import StreamValue
from wagtail.core.models import Page

import collections
import json
import re
from urllib.parse import urlencode, urlparse


def _find_block(stream_value, raw_data, block_id):
    for i in range(len(raw_data)):
        if raw_data[i]['id']==block_id:
            def set_value(val):
                stream_value[i].value = val
            return stream_value[i].block, stream_value[i].value, set_value, stream_value

        # is this a streamblock/listblock?
        if isinstance(raw_data[i]['value'], collections.Sequence) and len(raw_data[i]['value']) and hasattr(raw_data[i]['value'][0], 'get') and raw_data[i]['value'][0].get('id'):
            rb, rv, rsv, rp = _find_block(stream_value[i].value, raw_data[i]['value'], block_id)
            if rb:
                return rb, rv, rsv, rp

        #check structblock field values for any potential block lists
        if isinstance(raw_data[i]['value'], dict):
            for k, v in raw_data[i]['value'].items():
                if isinstance(v, collections.Sequence) and len(v) and hasattr(v[0], 'get') and v[0].get('id'):
                    rb, rv, rsv, rp = _find_block(stream_value[i].value[k], v, block_id)
                    if rb:
                        return rb, rv, rsv, rp

    return None, None, None, None

def find_block(stream_value, block_id):
    #returns Block, StreamValue.StreamChild, setter function to update value, parent StreamValue

    return _find_block(stream_value, stream_value.raw_data, block_id)

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
        if isinstance(blocks[i]['value'], collections.Sequence):
            for v in blocks[i]['value']:
                if isinstance(v, collections.Sequence) and len(v) and hasattr(v[0], 'get') and v[0].get('id'):
                    if modify_block(action, v, block_id):
                        #if block was moved, stop looking
                        return True

        #search through all fields for any potential block lists
        if isinstance(blocks[i]['value'], dict):
            for v in blocks[i]['value'].values():
                if isinstance(v, collections.Sequence) and len(v) and hasattr(v[0], 'get') and v[0].get('id'):
                    if modify_block(action, v, block_id):
                        #if block was moved, stop looking
                        return True

def get_latest_revision_and_save_function(obj):
    """
    For a given model instance, return the latest revision of that model
    instance, as well as a function which saves it, as a tuple.
    """
    save = obj.save
    if isinstance(obj, Page):
        if obj.has_unpublished_changes:
            # Save over the latest revision, not the published one
            obj = obj.get_latest_revision_as_page()
            
            def save():
                rev = obj.get_latest_revision()
                rev.content_json = obj.to_json()
                rev.save()
    return obj, save

def check_can_edit(user, obj):
    if hasattr(obj, 'permissions_for_user'):
        if not obj.permissions_for_user(user).can_edit():
            raise PermissionDenied
    elif not PermissionHelper(obj).user_can_edit_obj(user, obj):
        raise PermissionDenied

def render_edit_panel(request, d):
    # Steal all of the <script> and stylesheet tags from the admin base template
    admin_base = render_to_string("wagtailadmin/admin_base.html", request=request)
    script_tags = mark_safe("\n".join(re.findall('<script[^>]*>.*?</script>', admin_base, re.DOTALL)))
    stylesheet_tags = mark_safe("\n".join(re.findall('<link rel="stylesheet"[^>]+/?>', admin_base, re.DOTALL)))

    ret = render(request, "liveedit/edit_panel.html", {
        **d,
        'script_tags':script_tags,
        'stylesheet_tags':stylesheet_tags,
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
        return self.err


@csrf_exempt
@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def action_view(request):
    ct = ContentType.objects.get(pk=request.POST['content_type_id'])
    obj = ct.model_class().objects.get(pk=request.POST['object_id'])
    check_can_edit(request.user, obj)
    obj, save = get_latest_revision_and_save_function(obj)
    value = getattr(obj, request.POST['object_field'])

    block_id = request.POST['id']

    modify_block(request.POST['action'], value.raw_data, block_id)
    save()

    return HttpResponseRedirect(request.POST['redirect_url'])

@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def edit_block_view(request):
    from wagtail.admin.views.pages.edit import EditView
    view = EditView.as_view()

    ct = ContentType.objects.get(pk=request.GET['content_type_id'])
    obj = ct.model_class().objects.get(pk=request.GET['object_id'])
    check_can_edit(request.user, obj)
    obj, save = get_latest_revision_and_save_function(obj)
    value = getattr(obj, request.GET['object_field'])

    block, block_value, set_value, parent = find_block(value, request.GET['id'])

    errors = ErrorWrapper(None)
    if request.method=="POST" and request.POST.get('delete'):
        for i, block in enumerate(parent):
            if block_value==block.value:
                del parent[i]
                save()

                return ReloadResponse()
    elif request.method=="POST":
        val = block.value_from_datadict(request.POST, request.FILES, 'block_edit_form')
        try:
            val = block.clean(val)

            set_value(val)
            #print('val is', repr(val))
            #print('block_value is', repr(block_value))

            save()

            return ReloadResponse(request.GET['id'])

        except forms.ValidationError as e:
            errors = ErrorWrapper(e)
            block_value = val

    bw = BlockWidget(block)

    return render_edit_panel(request, {
        'form_html': bw.render_with_errors('block_edit_form', block_value, errors=errors), #block.render_form(block_value, prefix="block_edit_form", ),
        'form_media': bw.media,
    })

@permission_required('wagtailadmin.access_admin', login_url='wagtailadmin_login')
def append_block_view(request):
    ct = ContentType.objects.get(pk=request.GET['content_type_id'])
    obj = ct.model_class().objects.get(pk=request.GET['object_id'])
    check_can_edit(request.user, obj)
    obj, save = get_latest_revision_and_save_function(obj)
    value = getattr(obj, request.GET['object_field'])

    _, _, _, parent_value = find_block(value, request.GET['id'])

    parent_block = parent_value.stream_block
    blank_value = StreamValue(parent_value.stream_block, [])

    errors = None
    if request.method=="POST":
        val = parent_block.value_from_datadict(request.POST, request.FILES, 'block_edit_form')
        try:
            val = parent_block.clean(val)

            for i, v in enumerate(parent_value):
                if v.id==request.GET['id']:
                    #insert after this block
                    for j, added in enumerate(val):
                        parent_value.insert(i+1+j, added)

                        # The above insert call leaves the _raw_data entry as None,
                        # which will cause search indexing to error - Wagtail probably
                        # isn't expecting us to meddle with StreamValues like this.
                        #
                        # Thus we also need to populate the _raw_data entry manually.

                        parent_value._raw_data[i+1+j] = added.get_prep_value()
                    break

            save()

            return ReloadResponse()
        except forms.ValidationError as e:
            errors = ErrorList([e])
            blank_value = val

    bw = BlockWidget(parent_block)

    return render_edit_panel(request, {
        'form_html': bw.render_with_errors('block_edit_form', blank_value, errors=errors),
        'form_media': bw.media,
    })
