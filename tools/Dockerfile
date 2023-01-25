FROM python:3.11-slim

RUN pip install Django Pillow Willow pytz selenium

ARG WAGTAIL_VERSION

WORKDIR /work

RUN pip install wagtail==$WAGTAIL_VERSION

ADD manage.py /work/
ADD liveedit/ /work/liveedit/
ADD tests/ /work/tests/

#RUN python3 ./manage.py test --keepdb --help

CMD ["python3", "./manage.py", "test"]
