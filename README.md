# wagtail-liveedit

Allow StreamField blocks to be edited via your Wagtail site's frontend.

## Demo

<video src="https://user-images.githubusercontent.com/1122893/144843168-9ac50c50-6596-43bc-a1a6-53861e382ae0.mp4" width="962"></video>

## Requirements

- Wagtail (see supported versions below)
- Python 3.8+

## Supported versions

Wagtail version | Passing tests?
----------------|---------------
7.0.1           | :heavy_check_mark:
6.4.2           | :heavy_check_mark:
6.3.5           | :heavy_check_mark:
6.2.4           | :heavy_check_mark:
6.1.3           | :heavy_check_mark:
6.0.6           | :heavy_check_mark:
5.2.8           | :heavy_check_mark:

## Installation

1. Run `pip install wagtail-liveedit`

2. Add `'liveedit'` to INSTALLED_APPS.

3. Add:

    ```py
    url(r'^__liveedit__/', include('liveedit.urls')),
    ```

    to your app's `urls.py` urlpatterns list

4. In your templates, when rendering StreamFields, replace:

    ```py
    {% for block in page.body %}
        {% include_block block %}
    {% endfor %}
    ```

    with

    ```py
    {% load liveedit %}

    {% for block in page.body %}
        {% liveedit_include_block block object=page field="body" %}
    {% empty %}
        {% liveedit_insert_new object=page field="body" %}
    {% endfor %}
    ```

    where `page` is the model instance to which the StreamField belongs, and
`"body"` is the name of the StreamField on that model instance.

5. In your block templates, add `{% liveedit_attributes %}` inside the outermost
   opening HTML tag. For example:

    ```html
    {% load liveedit %}
    <div class="block-text" {% liveedit_attributes %}>    
        ...
    </div>
    ```

6. In your base template add:

    `{% liveedit_css %}`

    with the style tags inside the `<head>` and, 

    `{% liveedit_js %}`

    just before the closing `</body>` tag.

    (Also add `{% load liveedit %}` at the top).


## Alternate method without using `liveedit_include_block`

You can also make a StreamField block editable by supplying parameters to the
`liveedit_attributes` template tag directly:

```html
{% for block in page.body %}
    <div {% liveedit_attributes block object=page field="body" %}>
        {{ block.value.text }}
    </div>
{% endfor %}
```


## Notes

1. `wagtail-liveedit` is dependent on various Wagtail internals, such as the
   admin editor views and StreamValue methods. For this reason, this package's
   Wagtail version compatibility will only be updated after it has been tested
   against each individual Wagtail version.

2. Be careful if caching your rendered pages, since:
    - you don't want anonymous visitors seeing the liveedit controls (even
      though they won't have permission to alter anything)
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

3. To avoid every block edit resulting in a new page revision being created,
   `wagtail-liveedit` checks the age of the current revision, and the logged-in
   user. If the current revision was created over an hour ago, or the current
   revision was created by a different user, then editing a block will result in
   a new revision being published, otherwise the existing one will be modified.
   
   This effectively merges together all block edits made by a single user,
   within an hour of each other, into a single page revision.

4. `wagtail-liveedit` inserts an extra `<div>` tag for the editor controls at
   the beginning of each block. This can cause styling problems, if you are
   using `:first-child` selectors to match the content of blocks, as the
   expected first child will become the second. You can work around this by
   adding an extra selector:

    ```css
    .my-block > div:first-child,
    .my-block > .liveedit-bar:first-child + div {
    ```

## How it works

When you call `{% liveedit_include_block ... %}` to render the blocks in your
templates, extra data is passed through to the block template (via the context).
When you then use `{% liveedit_attributes %}` in your block template, if you
have sufficient permissions, this data is output as JSON within a custom
`data-liveedit` HTML attribute.

This extra data consists of:
- The content type of the model that the StreamField is on.
- The id of the model instance.
- The name of the StreamField on the model.
- The id of the block itself.

The frontend Javascript runs on page load, finds the blocks that have the
`data-liveedit` attribute, and adds interactive editor controls. If you click
the controls to edit a block, an iframe is created to load a form via the
backend API, populated with the indicated StreamField's current value. When you
then save the form, the backend finds the block within the indicated
StreamField, updates it, and resaves the model.
