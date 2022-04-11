from django.shortcuts import render

from .models import TestPage

def page_view(request):
    try:
        page = TestPage.objects.get(slug='test')

        return render(request, "page.html", {'page': page})
    except Exception as e:
        print(e)