#!python
# coding=utf-8
from setuptools import setup, find_packages

setup(
    name = 'httpd',
    version = '1.0',
    packages = find_packages(),
    package_data = {
        'httpd': ['templates/*.html'],
    },
    author = 'Gerald',
    author_email = 'gera2ld@163.com',
    description = 'Super light HTTP daemon in Python, using asyncio.',
    url = 'https://github.com/gera2ld/pyhttpd',
)
