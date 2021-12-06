#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='wagtail-liveedit',
      version='0.0.1',
      description='Live editing add-on for Wagtail CMS',
      author='jonny5532',
      license='MIT',
      url='https://github.com/jonny5532/wagtail-liveedit',
      packages=find_packages(),
      include_package_data=True,
      install_requires=[
          'wagtail>=2.13',
      ],
     )
