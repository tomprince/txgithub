# This file is part of txgithub.  txgithub is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from setuptools import setup

setup(
    name='txgithub',
    version='0.2.0',
    description='GitHub API client implemented using Twisted.',
    long_description=open('README.rst').read(),
    author='Tom Prince',
    author_email='tom.prince@ualberta.net',
    url='https://github.com/tomprince/txgithub',
    platforms='any',
    license='MIT',
    packages=['txgithub', 'txgithub.scripts'],
    scripts=['bin/gist', 'bin/get-github-token'],
    install_requires=[
        'twisted >= 12.3.0',
        'pyopenssl',
    ],
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Twisted',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
