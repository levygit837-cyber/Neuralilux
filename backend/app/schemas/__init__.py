"""Schema package.

Keep package imports lightweight; import concrete schema modules directly where
needed to avoid loading optional validation dependencies eagerly.
"""

__all__: list[str] = []
