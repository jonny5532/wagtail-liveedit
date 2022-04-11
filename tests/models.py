from wagtail.core import blocks
from wagtail.core.fields import StreamField
from wagtail.core.models import Page

class TestPage(Page):
    #class Meta:
        #app_label = 'tests'
        #managed = False

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

    ], null=True, blank=True)

