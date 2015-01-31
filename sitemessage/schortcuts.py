"""Compatibility module with misspelled name.

"""
import warnings

from .shortcuts import *

warnings.warn('Import from `schortcuts` module is deprecated. Please import from `shortcuts`.', DeprecationWarning)
