#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='wagtail-liveedit',
      version='0.0.4',
      description='Live editing add-on for Wagtail CMS',
      author='jonny5532',
      license='MIT',
      url='https://github.com/jonny5532/wagtail-liveedit',
      classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Framework :: Wagtail",
      ],
      packages=find_packages(exclude=['tests', 'tests.migrations']),
      include_package_data=True,
      install_requires=[
          'wagtail>=2.13',
      ],
     )
