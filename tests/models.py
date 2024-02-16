import wagtail
from wagtail.admin.panels import FieldPanel
try:
    from wagtail import blocks
    from wagtail.fields import StreamField
    from wagtail.models import Page
except ImportError:
    # Wagtail <5
    from wagtail.core import blocks
    from wagtail.core.fields import StreamField
    from wagtail.core.models import Page

STREAMFIELD_ARGS = dict(use_json_field=True) if wagtail.VERSION >= (3,) else {}

class TestPage(Page):
    template = 'page.html'

    body = StreamField([

        ('text', blocks.StructBlock([
            ('body', blocks.RichTextBlock(required=False)),
        ], template="text_block.html")),

        ('section', blocks.StreamBlock([
            ('text', blocks.StructBlock([
                ('body', blocks.RichTextBlock(required=False)),
            ], template="text_block.html")),
        ])),

        ('list', blocks.StructBlock([
            ('title', blocks.TextBlock(required=False)),
            ('items', blocks.StreamBlock([
                ('item', blocks.StructBlock([
                    ('body', blocks.RichTextBlock(required=False)),
                ], template="text_block.html")),
            ])),
        ])),

        ('columns', blocks.StructBlock([
            ('columns', blocks.ListBlock(
                blocks.StreamBlock([
                    ('text', blocks.StructBlock([
                        ('body', blocks.RichTextBlock(required=False)),
                    ])),
                ], template="text_block.html"),
                min_num=1, max_num=3,
            )),
        ])),

        ('required', blocks.StructBlock([
            ('text', blocks.TextBlock(required=True)),
        ])),

    ], **STREAMFIELD_ARGS, null=True, blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]
