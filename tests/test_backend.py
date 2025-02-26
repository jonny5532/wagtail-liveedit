from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.db import connection, transaction
from django.shortcuts import render
from django.template.loader import render_to_string
try:
    from django.test import RequestFactory
except ImportError:
    # Wagtail <3
    from django.tests import RequestFactory

try:
    from wagtail.models import Page
    from wagtail.rich_text import RichText
except ImportError:
    # Wagtail <5
    from wagtail.core.models import Page
    from wagtail.core.rich_text import RichText

try:
    from wagtail.test.utils import WagtailPageTests, WagtailTestUtils
    from wagtail.test.utils.form_data import nested_form_data, streamfield
except ImportError:
    # Wagtail <5
    from wagtail.tests.utils import WagtailPageTests, WagtailTestUtils
    from wagtail.tests.utils.form_data import nested_form_data, streamfield


from html.parser import HTMLParser
import json
import urllib.parse
import uuid

from liveedit import views

from .models import TestPage

class MockRequest:
    def __init__(self, user):
        self.user = user

class BackendTestCase(WagtailPageTests, WagtailTestUtils):
 
    def setUp(self):
        super(BackendTestCase, self).setUp()

        self.user = self.create_superuser(
            username='administrator',
            email='administrator@email.com',
            password='password'
        )
        self.user_without_perms = self.create_user(
            username='user',
            password='password',
            is_staff=True,
        )
        self.user_without_perms.user_permissions.add(
            ContentType.objects.get(app_label='wagtailadmin', model='admin').permission_set.get(codename='access_admin')
        )

        self.root_page = Page.objects.get(pk=1)

        self.test_page = TestPage()
        self.test_page.title = "Test"
        self.test_page.slug = 'test'
        self.test_page.body = json.dumps([
            {'type': 'text', 'id':str(uuid.uuid4()), 'value': {
                'body': "<h2>hello world</h2>"
            }},
            {'type': 'text', 'id':str(uuid.uuid4()), 'value': {
                'body': "<p>The first paragraph.</p>"
            }},
            {'type': 'section', 'id':str(uuid.uuid4()), 'value': [
                {'type': 'text', 'id':str(uuid.uuid4()), 'value': {
                    'body': "<p>Text inside a section.</p>"
                }},
                {'type': 'text', 'id':str(uuid.uuid4()), 'value': {
                    'body': "<p>A second text inside a section.</p>"
                }},
            ]},
            {'type': 'list', 'id':str(uuid.uuid4()), 'value': {
                'title': 'This is a list',
                'items': [
                    {'type': 'item', 'id':str(uuid.uuid4()), 'value': {
                        'body': '<p>Testing</p>'
                    }}
                ],
            }},

            {'type': 'required', 'id':str(uuid.uuid4()), 'value': {
                'text': 'This is text',
            }},

            {'type': 'columns', 'id':str(uuid.uuid4()), 'value': {
                'columns': [
                    {'type': 'item', 'id':str(uuid.uuid4()), 'value': [
                        {'type': 'text', 'id':str(uuid.uuid4()), 'value': {
                            'body': "<p>A text inside a column.</p>"
                        }},
                        {'type': 'text', 'id':str(uuid.uuid4()), 'value': {
                            'body': "<p>A second text inside a column.</p>"
                        }},
                    ]}
                ],
            }},
        ])
        self.root_page.add_child(instance=self.test_page)
        self.content_type = ContentType.objects.get_for_model(TestPage)

        self.empty_page = TestPage()
        self.empty_page.title = "Empty"
        self.empty_page.slug = 'empty'
        self.empty_page.body = json.dumps([])
        self.root_page.add_child(instance=self.empty_page)

    def test_liveedit_attributes(self):
        ret = render_to_string(
            "page.html", 
            {'page':self.test_page}, 
            request=MockRequest(self.user)
        )

        parent = self
        class MyHTMLParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if (tag=="div" 
                        and dict(attrs).get('class')=='block-text'
                        and dict(attrs).get('data-liveedit')):
                    if not hasattr(self, 'data_liveedit'):
                        self.data_liveedit = json.loads(dict(attrs).get('data-liveedit'))

            def check_tags(self):
                parent.assertEqual(self.data_liveedit['id'], parent.test_page.body[0].id)
                parent.assertEqual(self.data_liveedit['block_type'], parent.test_page.body[0].block_type)
                #check content type?
                parent.assertEqual(self.data_liveedit['object_field'], 'body')

        parser = MyHTMLParser()
        parser.feed(ret)
        parser.check_tags()

    def check_block_form(self, path, id=None):
        self.login(user=self.user)

        ret = self.client.get(path, {
            'content_type_id':self.content_type.id,
            'object_id':self.test_page.id,
            'object_field':'body',
            'id':id if id is not None else self.test_page.body[2].value[0].id,
        })

        parent = self
        class MyHTMLParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if (tag=="div" 
                        and dict(attrs).get('id')=='block_edit_form'
                        and dict(attrs).get('data-block')):
                    # Wagtail < 6.1
                    self.data_block = json.loads(dict(attrs).get('data-block'))
                elif (tag=="div" 
                        and dict(attrs).get('id')=='block_edit_form'
                        and dict(attrs).get('data-w-block-arguments-value')):
                    self.data_block = json.loads(dict(attrs).get('data-w-block-arguments-value'))[0]

            def check_tags(self):
                assert hasattr(self, 'data_block'), "Block edit form not found."
                assert self.data_block==[] or (isinstance(self.data_block, dict) and len(self.data_block))

        parser = MyHTMLParser()
        parser.feed(ret.content.decode('utf-8'))
        parser.check_tags()

    def test_block_edit_form(self):
        self.check_block_form('/__liveedit__/edit-block/')

    def test_block_append_form(self):
        self.check_block_form('/__liveedit__/append-block/')

    def test_block_edit_nested_form(self):
        """
        Attempt to edit a block inside a streamblock in a listblock in a streamblock.
        """
        self.login(user=self.user)

        ret = self.client.get('/__liveedit__/edit-block/', {
            'content_type_id':self.content_type.id,
            'object_id':self.test_page.id,
            'object_field':'body',
            'id':self.test_page.body[5].value['columns'][0][0].id,
        })

    def test_block_edit(self):
        self.login(user=self.user)

        ret = self.client.post('/__liveedit__/edit-block/?' + urllib.parse.urlencode({
            'content_type_id':self.content_type.id,
            'object_id':self.test_page.id,
            'object_field':'body',
            'id':self.test_page.body[0].id,
        }), {
            'block_edit_form-body':json.dumps({
                "blocks":[{
                    "text":"This is the replacement rich text.",
                }],
            })
        })

        self.assertIn('<p>This is the replacement rich text.</p>', str(TestPage.objects.get(pk=self.test_page.id).body))

    def test_block_edit_twice(self):
        # Should be no revisions at first
        self.assertEqual(self.test_page.revisions.count(), 0)
        
        # This should create a new revision
        self.test_block_edit()
        self.assertEqual(self.test_page.revisions.count(), 1)
        
        # The second time shouldn't create a new revision
        self.test_block_edit()
        self.assertEqual(self.test_page.revisions.count(), 1)

    def test_block_edit_draft(self):
        self.login(user=self.user)

        # Create a draft, which we'll modify
        draft = self.test_page.save_revision()

        # Update a block on the (draft) page
        ret = self.client.post('/__liveedit__/edit-block/?' + urllib.parse.urlencode({
            'content_type_id':self.content_type.id,
            'object_id':self.test_page.id,
            'object_field':'body',
            'id':self.test_page.body[0].id,
        }), {
            'block_edit_form-body':json.dumps({
                "blocks":[{
                    "text":"This is the replacement rich text.",
                }],
            })
        })

        # Check that the draft is still extant and unpublished
        self.assertTrue(TestPage.objects.get(pk=self.test_page.id).has_unpublished_changes)
        # Check that the draft got updated
        self.assertIn('<p>This is the replacement rich text.</p>', str(TestPage.objects.get(pk=self.test_page.id).get_latest_revision_as_object().body))
        # Check that the live page is unchanged
        self.assertNotIn('<p>This is the replacement rich text.</p>', str(TestPage.objects.get(pk=self.test_page.id).body))

        # Publish the draft
        TestPage.objects.get(pk=self.test_page.id).get_latest_revision().publish()
        # Check that the live page has updated
        self.assertIn('<p>This is the replacement rich text.</p>', str(TestPage.objects.get(pk=self.test_page.id).body))

    def check_block_errors(self, path, data):
        self.login(user=self.user)

        ret = self.client.post(path + '?' + urllib.parse.urlencode({
            'content_type_id':self.content_type.id,
            'object_id':self.test_page.id,
            'object_field':'body',
            'id':self.test_page.body[4].id,
        }), data)

        self.assertIn(b"This field is required.", ret.content)

    def test_block_edit_errors(self):
        return self.check_block_errors('/__liveedit__/edit-block/', {
            'block_edit_form-body':json.dumps({
                "blocks":[{
                    "text":"",
                }],
            }),
        })

    def test_block_append_errors(self):
        return self.check_block_errors('/__liveedit__/append-block/', {
            'block_edit_form-count': '1',
            'block_edit_form-0-deleted': '',
            'block_edit_form-0-order': '0',
            'block_edit_form-0-type': 'required',
            'block_edit_form-0-id': str(uuid.uuid4()),
            'block_edit_form-0-value-text': '',
        })

    def _do_action(self, block_id, action):
        self.login(user=self.user)

        ret = self.client.post('/__liveedit__/action/', {
            'content_type_id':self.content_type.id,
            'object_id':self.test_page.id,
            'object_field':'body',
            'id':block_id,
            'redirect_url':'/test/#le-' + block_id,
            'action':action,
        })

        return TestPage.objects.get(pk=self.test_page.id).body

    def test_block_move_down(self):
        block_id = self.test_page.body[0].id
        body = self._do_action(block_id, 'move_down')

        self.assertEqual(
            body[1].id,
            block_id,
        )

    def test_block_move_up(self):
        block_id = self.test_page.body[1].id
        body = self._do_action(block_id, 'move_up')

        self.assertEqual(
            body[0].id,
            block_id,
        )

    def test_block_delete(self):
        self.login(user=self.user)

        n = len(self.test_page.body)

        ret = self.client.post('/__liveedit__/edit-block/?' + urllib.parse.urlencode({
            'content_type_id':self.content_type.id,
            'object_id':self.test_page.id,
            'object_field':'body',
            'id':self.test_page.body[1].id,
        }), {
            'delete':'1'        
        })

        self.assertEqual(
            len(TestPage.objects.get(pk=self.test_page.id).body),
            n-1
        )

    def test_block_delete_nested(self):
        self.login(user=self.user)

        n = len(self.test_page.body[2].value)

        ret = self.client.post('/__liveedit__/edit-block/?' + urllib.parse.urlencode({
            'content_type_id':self.content_type.id,
            'object_id':self.test_page.id,
            'object_field':'body',
            'id':self.test_page.body[2].value[0].id,
        }), {
            'delete':'1'        
        })

        self.assertEqual(
            len(TestPage.objects.get(pk=self.test_page.id).body[2].value),
            n-1
        )

    def test_block_first_form(self):
        self.check_block_form('/__liveedit__/append-block/', id="")
        
    def test_unauthenticated(self):
        """
        Test that the liveedit attributes are not added when the user is not authenticated.
        """
        ret = render_to_string(
            "page.html", 
            {'page':self.test_page}, 
            request=MockRequest(AnonymousUser())
        )
        self.assertNotIn('data-liveedit', ret)

    def test_unauthenticated_empty_page(self):
        """
        Test that the liveedit attributes are not added when the user is not
        authenticated, for a page without any blocks (but with a new-block
        placeholder).
        """
        ret = render_to_string(
            "page.html", 
            {'page':self.empty_page}, 
            request=MockRequest(AnonymousUser())
        )
        self.assertNotIn('data-liveedit', ret)

    def test_insufficient_permission(self):
        self.login(user=self.user_without_perms)

        ret = self.client.post('/__liveedit__/edit-block/?' + urllib.parse.urlencode({
            'content_type_id':self.content_type.id,
            'object_id':self.test_page.id,
            'object_field':'body',
            'id':self.test_page.body[0].id,
        }), {
            'block_edit_form-body':json.dumps({
                "blocks":[{
                    "text":"This is the replacement rich text.",
                }],
            })
        })

        self.assertEqual(ret.status_code, 400)
        self.assertIn(b"Permission denied", ret.content)

