#!/usr/bin/env python
# run python3 setup.py develop
from setuptools import setup

setup(
    name="tjit",
    version="1.0.0",
    packages=["tjit"],
    entry_points={"console_scripts": ["tjit = tjit.cli:main"]},
)
