def is_enabled(request):
    """
    This is called before the liveedit functionality is inserted into a page.
    You can replace this function by adding the Django setting
    `LIVEEDIT_ENABLED_CHECK` pointing to a function in your own code.

    You may wish to only enable liveedit in certain circumstances by checking a
    condition here. 
    
    You may also want to perform your own admin-only cookie check here, to avoid
    `request.user` being accessed by the subsequent `is_authenticated` check,
    since this will access the session, setting the `Vary: Cookie` header and
    spoiling the cacheability of the page.

    """
    return True
