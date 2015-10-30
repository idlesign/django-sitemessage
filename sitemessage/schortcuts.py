"""Compatibility module with misspelled name.

"""
import warnings

from .shortcuts import *

warnings.warn(
    'Import from `schortcuts` module is deprecated. '
    'Will be removed in 1.0. Please import from `shortcuts`.', DeprecationWarning)
