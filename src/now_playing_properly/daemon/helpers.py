from typing import Any
from functools import singledispatch
from ..common.plugin_types import UnixFD


def traverse_plugin_data_dict(
    data_dict: dict[str, Any], namespace: str = "npp_plugins"
) -> dict[str, Any]:
    # More Robust Implementation that avoids actual recursion
    finished_dict = {}
    # Breadth first search, stack tracks how many namespaces this namespace has
    stack = [(data_dict, namespace)]
    # Since python allows dict to reference itself, this prevents an infinite loop as a reference will have the same id as the original
    visited = {id(data_dict)}

    while stack:
        current_dict, current_namespace = stack.pop()

        for key, value in current_dict.items():
            this_namespace = f"{current_namespace}:{key}"
            if isinstance(value, dict):
                obj_id = id(value)
                # If we have visited this namespace before, skip it
                if obj_id in visited:
                    continue
                visited.add(obj_id)
                stack.append((value, this_namespace))
            else:
                finished_dict[this_namespace] = value

    return finished_dict


def get_int_sig(val: int) -> str:
    """Returns unsigned types (y, q, u, t) when non-negative, else signed (n, i, x)."""
    if val >= 0:
        if val <= 0xFFFF:
            return "q"
        if val <= 0xFFFFFFFF:
            return "u"
        if val <= 0xFFFFFFFFFFFFFFFF:
            return "t"
        raise ValueError(f"Value {val} exceeds UINT64")
    else:
        if val >= -(2**15):
            return "n"
        if val >= -(2**31):
            return "i"
        if val >= -(2**63):
            return "x"
        raise ValueError(f"Value {val} exceeds INT64")


@singledispatch
def wrap(data: Any) -> tuple[str, Any]:
    raise TypeError(f"Unsupported type: {type(data).__name__}")


@wrap.register
def _(data: bool) -> tuple[str, Any]:
    return "b", data


@wrap.register
def _(data: int) -> tuple[str, Any]:
    return get_int_sig(data), data


@wrap.register
def _(data: float) -> tuple[str, Any]:
    return "d", data


@wrap.register
def _(data: str) -> tuple[str, Any]:
    return "s", data


@wrap.register(bytes)
@wrap.register(bytearray)
def _(data: bytes | bytearray) -> tuple[str, Any]:
    return "ay", data


@wrap.register
def _(data: tuple) -> tuple[str, Any]:
    if not data:
        return "()", ()
    sigs, vals = zip(*(wrap(item) for item in data))
    return f"({''.join(sigs)})", tuple(vals)


@wrap.register(list)
@wrap.register(set)
def _(data: list | set) -> tuple[str, Any]:
    if not data:
        return "av", []

    wrapped = [wrap(x) for x in data]
    unique_sigs = {sig for sig, _ in wrapped}

    if len(unique_sigs) == 1:
        return f"a{unique_sigs.pop()}", [val for _, val in wrapped]
    return "av", wrapped


# We assume a flat dict here, if theres any nested dicts we will raise an error
def tovariant(data_dict: dict[str, Any]):
    variant_packed_dict: dict[str, tuple[str, Any]] = {}
    for key, value in data_dict.items():
        variant_packed_dict[key] = wrap(value)
    return variant_packed_dict


def prep_metadata(
    metadata_dict: dict[str, Any], plugin_data_dict: dict[str, Any]
) -> dict[str, tuple[str, Any]]:
    plugin_metadata_flattened = traverse_plugin_data_dict(plugin_data_dict)
    metadata_dict.update(plugin_metadata_flattened)
    return tovariant(metadata_dict)
