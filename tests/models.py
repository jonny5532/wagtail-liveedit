try:
    from wagtail import blocks
    from wagtail.fields import StreamField
    from wagtail.models import Page
except ImportError:
    # Wagtail <5
    from wagtail.core import blocks
    from wagtail.core.fields import StreamField
    from wagtail.core.models import Page

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

    ], use_json_field=True, null=True, blank=True)

