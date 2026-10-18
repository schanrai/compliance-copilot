"""YAML loading that rejects repeated mapping keys.

Plain `yaml.safe_load` keeps the last value of a repeated key without
warning, so a golden-set case or a manifest could silently lose an entry.
"""

from __future__ import annotations

from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode


class _NoDuplicateKeysLoader(yaml.SafeLoader):
    """Safe loader that rejects repeated mapping keys."""


def _construct_mapping_without_duplicates(
    loader: _NoDuplicateKeysLoader, node: MappingNode, deep: bool = False
) -> dict[Any, Any]:
    seen: set[Any] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            is_repeat = key in seen
        except TypeError:
            break  # unhashable key; construct_mapping reports it
        if is_repeat:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


_NoDuplicateKeysLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_without_duplicates,
)


def load_strict_yaml(text: str) -> Any:
    """Parse `text` as YAML. Raises `yaml.YAMLError` on invalid YAML or a repeated key."""

    return yaml.load(text, Loader=_NoDuplicateKeysLoader)
