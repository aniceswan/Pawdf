"""Pawdf's PDF operations. No GUI toolkit is imported anywhere below this
package, and no feature imports another feature.

Each subdirectory is a self-contained tool with its own README explaining how
to lift it into another project. `_shared/` is the only thing they have in
common. `registry.py` describes them all without importing any of them.
"""

from pawdf.core.registry import FEATURES, Feature, by_id, load

__all__ = ["FEATURES", "Feature", "by_id", "load"]
