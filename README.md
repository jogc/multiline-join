multiline-join
==============

QGIS plugin for merging the parts of multipolylines. For every polyline feature with multiple parts in the active layer it tries to reduce the number of parts as much as possible. It does this by fusing overlapping end vertices together. Vertices need to be at the exact same position to be considered overlapping. Parts with ambiguities will be removed. It operates on the currently selected features, or all features if none is selected.
