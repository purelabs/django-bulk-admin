import os
from setuptools import setup, find_packages

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='django-bulk-admin',
    version='0.1',
    packages=find_packages(exclude=('example_project*', 'screenshots',)),
    include_package_data=True,
    license='BSD',
    description='Django bulk admin enables you to bulk add, bulk edit, bulk upload and bulk select in django admin.',
    long_description=README,
    url='https://github.com/purelabs/django-bulk-admin',
    author='Ruben Grill',
    author_email='ruben.grill@gmail.com',
    install_requires=[
        'Django>=1.8.0',
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
