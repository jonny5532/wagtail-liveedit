FROM python:3.11-slim

# Pin Django 5.1.8 since Wagtail <= 6.2.3 is not compatible with Django 5.2
RUN pip install Django==5.1.8 Pillow Willow pytz selenium==4.10.0

ARG WAGTAIL_VERSION

WORKDIR /work

RUN pip install wagtail==$WAGTAIL_VERSION

ADD manage.py /work/
ADD liveedit/ /work/liveedit/
ADD tests/ /work/tests/

CMD ["python3", "./manage.py", "test"]
