# setup for zipls package

import os.path
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

setup(
        name='zipls',
        version='0.1',
        description='ls inside of a zip file',
        author='Matthew Clapp',
        author_email='itsayellow+dev@gmail.com',
        license='MIT',
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3'
            ],
        keywords='zip ls',
        py_modules=['zipls'],
        entry_points={
            'console_scripts':[
                'zipls=zipls:cli'
                ]
            },
        python_requires='>=3',
        )


