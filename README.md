# wagtail-liveedit

Allow StreamField blocks to be edited via your Wagtail site's frontend.

## Demo

<video src="https://user-images.githubusercontent.com/1122893/144843168-9ac50c50-6596-43bc-a1a6-53861e382ae0.mp4" width="962"></video>

## Requirements

Wagtail (see compatibility matrix below)
Python 3.8+

## Compatibility matrix

Wagtail version | Passing tests?
----------------|---------------
6.0.1           | :heavy_check_mark:
5.2.3           | :heavy_check_mark:
5.1.3           | :heavy_check_mark:
5.0.5           | :heavy_check_mark:
4.1.9           | :heavy_check_mark:
4.2.4           | :heavy_check_mark:
4.0.4           | :heavy_check_mark:

## Installation

1. Add `'liveedit'` to INSTALLED_APPS.

2. Add:

```
    url(r'^__liveedit__/', include('liveedit.urls')),
```
to your app's `urls.py` urlpatterns list

3. In your templates, when rendering StreamFields, replace:

`{% include_block block %}`

with

`{% liveedit_include_block block object=page field="body" %}`

where `page` is the model instance to which the StreamField belongs, and `"body"` is the name of the StreamField on that model instance.

(Also add `liveedit` to the `{% load ... %}` at the top).

4. In your block templates, add `{% liveedit_attributes %}` inside the outermost opening HTML tag. For example:

```
<div class="block-text" {% liveedit_attributes %}>
    ...
</div>
```

(Also add `liveedit` to the `{% load ... %}` at the top).

5. In your base template add:

`{% liveedit_css %}`

with the style tags in the `<head>` and, 

`{% liveedit_js %}`

just before the closing `</body>` tag.

(Also add `liveedit` to the `{% load ... %}` at the top).


## How it works

When each block is rendered in your templates, it is annotated with a reference to the underlying StreamValue which contains the block data. This allows the block data to be retrieved when you edit it, and overwritten when you save.

To reference a block's StreamValue we need four pieces of data:
- The content type of the model that the StreamField is on.
- The id of the model instance.
- The name of the StreamField on the model.
- The uuid of the block itself.

When rendering a block in a template, the normal Wagtail `{% include_block block %}` tag needs to be replaced by `{% liveedit_include_block block object=<model instance> field=<field name> %}`. The model instance and field name are stored in the rendering context, and in conjunction with the block itself, provide all of the information needed to reference the block's StreamValue.

When rendering a block template, the `{% liveedit_attributes %}` outputs the reference as a data-* HTML attribute on the block's outermost HTML tag which can then be read from Javascript.

After the page is rendered, the Javascript will run and decorate each block that has the liveedit attributes with editing controls that appear on hover.
