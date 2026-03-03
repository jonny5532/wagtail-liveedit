import json
from django.test import TestCase, RequestFactory
from django.utils import timezone
from django.contrib.auth import get_user_model
from wagtail.models import Page
from liveedit.forms import get_latest_revision_and_save_function
from tests.models import TestPage
from datetime import timedelta

User = get_user_model()

class RevisionSaveFunctionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user1 = User.objects.create_superuser(username='user1', email='user1@test.com', password='password')
        self.user2 = User.objects.create_superuser(username='user2', email='user2@test.com', password='password')
        self.root_page = Page.objects.get(id=1)
        self.page = TestPage(
            title="Test Page",
            slug="test-page",
            body=json.dumps([
                {'type': 'text', 'value': {'body': '<p>Initial content</p>'}}
            ])
        )
        self.root_page.add_child(instance=self.page)
        self.page.save_revision().publish()

    def test_updates_existing_draft_if_same_user_and_recent(self):
        request = self.factory.get('/')
        request.user = self.user1
        
        # Set some unpublished changes
        self.page.body = json.dumps([
            {'type': 'text', 'value': {'body': '<p>Draft content</p>'}}
        ])
        revision = self.page.save_revision(user=self.user1)
        self.page.refresh_from_db()
        
        # Sanity check
        self.assertTrue(self.page.has_unpublished_changes)
        
        # Get the revision as an object and a save function
        rev_as_obj, save = get_latest_revision_and_save_function(self.page, request)
        
        # Should return the object from the latest revision
        self.assertEqual(str(rev_as_obj.body[0].value['body']), "<p>Draft content</p>")
        
        # Modify the object and save
        rev_as_obj.body = [
            {'type': 'text', 'value': {'body': '<p>Updated draft content</p>'}}
        ]
        
        # Verify it was updated in memory
        self.assertEqual(str(rev_as_obj.body[0].value['body']), "<p>Updated draft content</p>")
        
        save()
        
        # Check that the existing revision was updated
        self.page.refresh_from_db()
        new_rev = self.page.get_latest_revision()
        new_obj = new_rev.as_object()
        self.assertEqual(str(new_obj.body[0].value['body']), "<p>Updated draft content</p>")
        
        # Check that it's still not published
        self.page.refresh_from_db()
        self.assertNotIn("Updated draft content", str(self.page.body))

    def test_creates_new_revision_if_different_user(self):
        # Ensure has_unpublished_changes is False by publishing
        self.page.save_revision(user=self.user1).publish()
        self.page.refresh_from_db()
        self.assertFalse(self.page.has_unpublished_changes)
        
        request = self.factory.get('/')
        request.user = self.user2 # Different user
        
        initial_revision_count = self.page.revisions.count()
        
        # Get the revision as an object and a save function
        obj, save = get_latest_revision_and_save_function(self.page, request)
        
        # Modify and save
        obj.body = json.dumps([
            {'type': 'text', 'value': {'body': '<p>User 2 content</p>'}}
        ])
        save()
        
        # Should have created and published a new revision
        self.assertEqual(self.page.revisions.count(), initial_revision_count + 1)
        self.page.refresh_from_db()
        self.assertEqual(str(self.page.body[0].value['body']), "<p>User 2 content</p>")
        self.assertEqual(self.page.get_latest_revision().user, self.user2)

    def test_creates_new_revision_if_time_elapsed(self):
        request = self.factory.get('/')
        request.user = self.user1
        
        # Need has_unpublished_changes to be False
        self.page.refresh_from_db()
        self.assertFalse(self.page.has_unpublished_changes)
        
        # Ensure the latest revision is old
        revision = self.page.get_latest_revision()
        old_time = timezone.now() - timedelta(hours=2)
        revision.created_at = old_time
        revision.save()
        
        initial_revision_count = self.page.revisions.count()
        
        # Get the revision as an object and a save function
        obj, save = get_latest_revision_and_save_function(self.page, request)
        
        # Modify and save
        obj.body = json.dumps([
            {'type': 'text', 'value': {'body': '<p>Timed out content</p>'}}
        ])
        save()
        
        # Should have created a new one
        self.assertEqual(self.page.revisions.count(), initial_revision_count + 1)
        self.page.refresh_from_db()
        self.assertEqual(str(self.page.body[0].value['body']), "<p>Timed out content</p>")

    def test_updates_published_page_directly_if_not_page(self):
        # Non-page subclasses don't get the extra logic, they just update
        # directly

        class MockObj:
            def __init__(self):
                self.save_called = False
                self.last_published_at = None
            def save(self):
                self.save_called = True
        
        obj = MockObj()
        returned_obj, save = get_latest_revision_and_save_function(obj, None)
        
        self.assertEqual(returned_obj, obj)
        save()
        self.assertTrue(obj.save_called)
        self.assertIsNotNone(obj.last_published_at)
