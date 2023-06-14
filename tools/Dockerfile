FROM python:3.11-slim

RUN pip install Django Pillow Willow pytz selenium==4.10.0

ARG WAGTAIL_VERSION

WORKDIR /work

RUN pip install wagtail==$WAGTAIL_VERSION

ADD manage.py /work/
ADD liveedit/ /work/liveedit/
ADD tests/ /work/tests/

CMD ["python3", "./manage.py", "test"]
