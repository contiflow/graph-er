# -*- coding: utf-8 -*-
"""
Repository layout anchors for RELATER.

The original code assumed the process current working directory was the inner
``RELATER/`` package directory so that ``../data`` and ``../out`` resolved
correctly. These constants anchor paths to the outer project folder (the one
that contains ``data/`` and ``out/``), so pipelines can be launched from any CWD.
"""
import os

_INNER_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
# Inner package lives at .../RELATER/RELATER/; repo root is one level up.
REPO_ROOT = os.path.abspath(os.path.join(_INNER_PACKAGE_DIR, os.pardir))

DATA_ROOT = os.path.join(REPO_ROOT, 'data')
OUT_ROOT = os.path.join(REPO_ROOT, 'out')
