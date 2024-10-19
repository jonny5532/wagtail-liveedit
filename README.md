# wagtail-liveedit

Allow StreamField blocks to be edited via your Wagtail site's frontend.

## Demo

<video src="https://user-images.githubusercontent.com/1122893/144843168-9ac50c50-6596-43bc-a1a6-53861e382ae0.mp4" width="962"></video>

## Requirements

- Wagtail (see compatibility matrix below)
- Python 3.8+

## Compatibility matrix

Wagtail version | Passing tests?
----------------|---------------
6.2.2           | :heavy_check_mark:
6.1.3           | :heavy_check_mark:
6.0.6           | :heavy_check_mark:
5.2.6           | :heavy_check_mark:
5.1.3           | :heavy_check_mark:
5.0.5           | :heavy_check_mark:
4.2.4           | :heavy_check_mark:
4.1.9           | :heavy_check_mark:

## Installation

1. Add `'liveedit'` to INSTALLED_APPS.

2. Add:

    ```py
    url(r'^__liveedit__/', include('liveedit.urls')),
    ```

    to your app's `urls.py` urlpatterns list

3. In your templates, when rendering StreamFields, replace:

    ```py
    {% include_block block %}
    ```

    with

    ```py
    {% liveedit_include_block block object=page field="body" %}
    ```

    where `page` is the model instance to which the StreamField belongs, and
`"body"` is the name of the StreamField on that model instance.

    (Also add `liveedit` to the `{% load ... %}` at the top).

4. In your block templates, add `{% liveedit_attributes %}` inside the outermost
   opening HTML tag. For example:

    ```html
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


## Alternate method without using `liveedit_include_block`

You can also make a StreamField block editable by supplying parameters to the
`liveedit_attributes` template tag directly:

```html
{% for block in page.body %}
    <div {% liveedit_attributes block object=page field="body">
        {{ block.value.text }}
    </div>
{% endfor %}
```


## Notes

1. `wagtail-liveedit` is dependent on various Wagtail internals, such as the admin editor views and StreamValue methods. For this reason, this package's Wagtail version compatibility will only be updated after it has been tested against each individual Wagtail version.

2. Be careful if caching your rendered pages, since:
    - you don't want anonymous visitors seeing the liveedit controls (even though they won't have permission to alter anything)
    - you will want admins to see their changes reflected immediately

    The easiest approach is to disable caching of rendered pages if the user is
    logged in, which can be done with middleware:

    ```py
    def cache_helper_middleware(get_response):
        def middleware(request):
            response = get_response(request)
            if request.user.is_authenticated:
                response['Cache-Control'] = 'no-cache'
            return response
        return middleware
    ```

3. To avoid every block edit resulting in a new page revision being created, `wagtail-liveedit` checks the age of the current revision, and the logged-in user. If the current revision was created over an hour ago, or the current revision was created by a different user, then editing a block will result in a new revision being published, otherwise the existing one will be modified.

    This effectively merges together all block edits made by a single user, within an hour of each other, into a single page revision.

4. `wagtail-liveedit` inserts an extra `<div>` tag at the beginning of each block, when a page is editable by the current user. This can cause styling problems, if you are using `:first-child` selectors to match the content of blocks, as the previous first child will become the second. You can work around this by adding an extra selector:

    ```css
    .my-block > div:first-child,
    .my-block > .liveedit-bar:first-child + div {
    ```

## How it works

When each block is rendered in your templates, it is annotated with a reference
to the underlying StreamValue which contains the block data. This allows the
block data to be retrieved when you edit it, and overwritten when you save.

To reference a block's StreamValue we need four pieces of data:
- The content type of the model that the StreamField is on.
- The id of the model instance.
- The name of the StreamField on the model.
- The uuid of the block itself.

When rendering a block in a template, the normal Wagtail `{% include_block block
%}` tag needs to be replaced by `{% liveedit_include_block block object=<model
instance> field=<field name> %}`. The model instance and field name are stored
in the rendering context, and in conjunction with the block itself, provide all
of the information needed to reference the block's StreamValue.

When rendering a block template, the `{% liveedit_attributes %}` outputs the
reference as a data-* HTML attribute on the block's outermost HTML tag which can
then be read from Javascript.

After the page is rendered, the Javascript will run and decorate each block that
has the liveedit attributes with editing controls that appear on hover.
