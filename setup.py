"""Setup for pip"""
# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from setuptools import setup


setup(
    name='clusterfuzz',
    version='0.2rc1',
    description="The command-line tools for ClusterFuzz's users",
    author='Google Inc.',
    license='Apache 2.0',
    packages=['clusterfuzz', 'clusterfuzz.commands'],
    entry_points={
        'console_scripts': [
            'clusterfuzz = clusterfuzz.main:execute'
        ]
    },
    install_requires=[
        'crcmod==1.7',
        'httplib2==0.10.3',
        'oauth2client==4.0.0',
        'urlfetch==1.0.2',
        'psutil==5.2.0',
        'pyOpenSSL==16.2.0',
        'xvfbwrapper==0.2.9',
        'requests==2.13.0'
    ],
    classifiers=[
        'Programming Language :: Python :: 2.7'],
    include_package_data=True)
