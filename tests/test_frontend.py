from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.servers.basehttp import WSGIServer
from django.db import connections, transaction
from django.test import LiveServerTestCase
from django.test.testcases import LiveServerThread, QuietWSGIRequestHandler

from wagtail.core.models import Page
from wagtail.tests.utils import WagtailPageTests, WagtailTestUtils

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.proxy import Proxy, ProxyType

import json
import os
import socket
import time
import uuid

from .models import TestPage

hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)

class LiveServerSingleThread(LiveServerThread):
    """Runs a single threaded server rather than multi threaded. Reverts https://github.com/django/django/pull/7832"""

    def _create_server(self):
        """
        the keep-alive fixes introduced in Django 2.1.4 (934acf1126995f6e6ccba5947ec8f7561633c27f)
        cause problems when serving the static files in a stream.
        We disable the helper handle method that calls handle_one_request multiple times.
        """
        QuietWSGIRequestHandler.handle = QuietWSGIRequestHandler.handle_one_request

        return WSGIServer((self.host, self.port), QuietWSGIRequestHandler, allow_reuse_address=False)


class LiveServerSingleThreadedTestCase(StaticLiveServerTestCase):
    "A thin sub-class which only sets the single-threaded server as a class"
    server_thread_class = LiveServerSingleThread

class FrontendTest(LiveServerSingleThreadedTestCase, WagtailPageTests, WagtailTestUtils):
    host = '0.0.0.0'
    port = 31411

    def setUp(self):
        super(FrontendTest, self).setUp()

        # user = get_user_model().objects.create(username='testuser', is_staff=True)
        # user.set_password('testpassword')
        # user.save()

        self.live_server_url = 'http://%s:%d'%(local_ip, self.port)

        opts = Options()
        opts.headless = True
        opts.add_argument('--disable-web-security') # avoid CORS problems
        opts.add_argument('--disable-site-isolation-trials')
        self.driver = webdriver.Remote(
            command_executor='http://%s:4444/wd/hub'%os.getenv('SELENIUM_HOST'),
            desired_capabilities=DesiredCapabilities.CHROME,
            options=opts,
            #proxy=proxy
        )
        self.driver.set_window_size(1280, 800)

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

        self.driver.implicitly_wait(1) #set timeout for finding elements

        self.driver.get(self.live_server_url + '/admin/?next=/404')
        self.xpath("//input[@name='username']").send_keys('administrator')
        self.xpath("//input[@name='password']").send_keys('password')
        self.xpath("//input[@name='password']").submit()

    def tearDown(self):
        self.driver.quit()
        super(FrontendTest, self).tearDown()

    def sel(self, sel):
        return self.driver.find_element_by_css_selector(sel)

    def xpath(self, sel):
        return self.driver.find_element_by_xpath(sel)

    def hover(self, el):
        ActionChains(self.driver).move_to_element(el).perform()

    def test_edit(self):
        self.driver.get(self.live_server_url + '/page/')

        self.hover(self.sel('.block-text'))
        self.xpath('//button[text()="Edit"]').click()

        time.sleep(1) #wait for editor to load

        self.driver.switch_to.frame(self.driver.find_elements_by_tag_name("iframe")[0])

        h2 = self.sel('h2')
        h2.click()
        h2.send_keys('extra_header_text')

        time.sleep(1) #wait for Draftail to update

        self.sel('input[value="Save"]').click()

        time.sleep(1) #wait for save to stick

        h2_contents = TestPage.objects.get(pk=self.test_page.id).body.raw_data[0]['value']['body']
        assert 'extra_header_text' in h2_contents


        #self.driver.switch_to.frame(0)

        #h2 = self.sel('h2')     

        #self.driver.save_screenshot('/tmp/ss.png')
        #time.sleep(300)

        #self.driver.get(self.live_server_url + '/static/js/liveedit.js')
        #print(self.driver.page_source)
