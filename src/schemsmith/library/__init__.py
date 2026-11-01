"""Parametric module library (redstone circuits, farms, buildings).

>>> from schemsmith.library import get_module
>>> region = get_module("t_flip_flop").build()  # doctest: +SKIP
"""

from schemsmith.library import buildings, farms, redstone, timer
from schemsmith.library.base import MODULES, Module, Param, get_module, register

__all__ = [
    "MODULES",
    "Module",
    "Param",
    "buildings",
    "farms",
    "get_module",
    "redstone",
    "register",
    "timer",
]
