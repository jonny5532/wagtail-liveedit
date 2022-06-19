from django.contrib.contenttypes.models import ContentType
from django.db import connection, transaction
from django.shortcuts import render
from django.template.loader import render_to_string
from django.test import RequestFactory

from wagtail.core.models import Page
from wagtail.core.rich_text import RichText
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
    # @classmethod
    # def setUpClass(cls):
    #     with connection.schema_editor() as schema_editor:
    #         schema_editor.create_model(TestPage)
    #         ContentType.objects.get_for_model(TestPage)
    #     super().setUpClass()

    # @classmethod
    # def tearDownClass(cls):
    #     super().tearDownClass()
    #     with connection.schema_editor() as editor:
    #         editor.delete_model(TestPage)
    #     connection.close()

    def setUp(self):
        super(BackendTestCase, self).setUp()

        self.user = self.create_superuser(
            username='administrator',
            email='administrator@email.com',
            password='password'
        )
        self.root_page = Page.objects.get(pk=1)

        self.test_page = TestPage()
        self.test_page.title = "Test"
        self.test_page.slug = 'test'
        self.test_page.body = json.dumps([
            {'type': 'text', 'id':str(uuid.uuid4()), 'value': {
                'body': "<h2>hello world</h2>"
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
        ])
        self.root_page.add_child(instance=self.test_page)
        self.content_type = ContentType.objects.get_for_model(TestPage)

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

    def test_block_edit_form(self):
        self.login(user=self.user)

        ret = self.client.get('/__liveedit__/edit-block/', {
            'content_type_id':self.content_type.id,
            'object_id':self.test_page.id,
            'object_field':'body',
            'id':self.test_page.body[1].value[0].id,
        })

        parent = self
        class MyHTMLParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if (tag=="div" 
                        and dict(attrs).get('id')=='block_edit_form'
                        and dict(attrs).get('data-block')):
                    self.data_block = json.loads(dict(attrs).get('data-block'))

            def check_tags(self):
                assert isinstance(self.data_block, dict)
                assert len(self.data_block)

        parser = MyHTMLParser()
        parser.feed(ret.content.decode('utf-8'))
        parser.check_tags()

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

        #print(str(TestPage.objects.get(pk=self.test_page.id).body))
        assert '<p>This is the replacement rich text.</p>' in str(TestPage.objects.get(pk=self.test_page.id).body)

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

        n = len(self.test_page.body[1].value)

        ret = self.client.post('/__liveedit__/edit-block/?' + urllib.parse.urlencode({
            'content_type_id':self.content_type.id,
            'object_id':self.test_page.id,
            'object_field':'body',
            'id':self.test_page.body[1].value[0].id,
        }), {
            'delete':'1'        
        })

        self.assertEqual(
            len(TestPage.objects.get(pk=self.test_page.id).body[1].value),
            n-1
        )
