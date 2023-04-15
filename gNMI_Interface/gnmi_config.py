"""Utility classes for representation of gNMI device configuration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
import typing as t

from confd_gnmi_common import add_path_prefix, make_formatted_path

import gnmi_pb2 as gnmi


T = t.TypeVar('T', bound='GNMIConfig')


class UpdateType(Enum):
    NONE = (0, '')
    VALUE = (1, 'value update')
    STRUCTURE = (2, 'structural update')

    def __init__(self, order: int, message: str) -> None:
        self.order = order
        self.message = message

    def __le__(self, other: UpdateType) -> bool:
        return self.order <= other.order

    def __add__(self, other: UpdateType) -> UpdateType:
        return self if self.value >= other.value else other


class GNMIConfig(ABC, t.Generic[T]):
    @abstractmethod
    def update(self, elems: t.List[gnmi.PathElem],
               index: int, value: gnmi.TypedValue) -> UpdateType: ...

    @abstractmethod
    def covered(self, other_config: T) -> bool: ...


class GNMIConfigTree(GNMIConfig['GNMIConfigTree']):
    def __init__(self) -> None:
        self.tree: t.Dict[str, GNMIConfig] = {}

    @staticmethod
    def new_child(elems: t.List[gnmi.PathElem], index: int) -> GNMIConfig:
        if index + 1 == len(elems):
            return GNMIConfigValue()
        elif elems[index].key:
            return GNMIConfigList(elems[index].key)
        else:
            return GNMIConfigTree()

    def update(self, elems: t.List[gnmi.PathElem],
               index: int, value: gnmi.TypedValue) -> UpdateType:
        assert index < len(elems)
        elem = elems[index]
        if elem.name in self.tree:
            child = self.tree[elem.name]
            utype = UpdateType.NONE
        else:
            child = self.new_child(elems, index)
            self.tree[elem.name] = child
            utype = UpdateType.STRUCTURE
        return child.update(elems, index + 1, value) + utype

    def covered(self, other_tree: GNMIConfigTree) -> bool:
        return False


class GNMIConfigList(GNMIConfig['GNMIConfigList']):
    def __init__(self, initial_keyset: t.Dict[str, str]) -> None:
        self.keys: t.Tuple[str, ...] = tuple(initial_keyset.keys())
        self.instances: t.Dict[t.Tuple[str, ...], GNMIConfig] = {}

    def update(self, elems: t.List[gnmi.PathElem],
               index: int, value: gnmi.TypedValue) -> UpdateType:
        assert 0 < index
        assert elems[index-1].key
        keyvals: t.Tuple[str, ...] = tuple(elems[index-1].key[k] for k in self.keys)
        if keyvals in self.instances:
            child = self.instances[keyvals]
            utype = UpdateType.NONE
        else:
            if index == len(elems):
                child = GNMIConfigValue()
            else:
                child = GNMIConfigTree()
            self.instances[keyvals] = child
            utype = UpdateType.STRUCTURE
        return child.update(elems, index, value) + utype

    def covered(self, other_tree: GNMIConfigList) -> bool:
        return False


class GNMIConfigValue(GNMIConfig['GNMIConfigValue']):
    def __init__(self) -> None:
        self.value: gnmi.TypedValue = gnmi.TypedValue()

    def update(self, elems: t.List[gnmi.PathElem],
               index: int, value: gnmi.TypedValue) -> UpdateType:
        assert index == len(elems)
        if self.value == value:
            return UpdateType.NONE
        self.value = value
        return UpdateType.VALUE

    def covered(self, other_tree: GNMIConfigValue) -> bool:
        return True


def verify_update(config: GNMIConfig, path: gnmi.Path, update: gnmi.Update,
                  minimal_update: UpdateType) -> None:
    if not minimal_update <= config.update(path.elem, 0, update.val):
        up_str = f'{make_formatted_path(path)} = {update.val}'
        if minimal_update == UpdateType.STRUCTURE:
            msg = f'expected structural update, received: {up_str}'
        else:
            msg = f'received non-update: {up_str}'
        raise AssertionError(msg)


def apply_response(config: GNMIConfig, response: gnmi.SubscribeResponse,
                   minimal_update: UpdateType = UpdateType.NONE) -> bool:
    notif = response.update
    have_updates = False
    for update in notif.update:
        have_updates = True
        path = add_path_prefix(update.path, notif.prefix)
        verify_update(config, path, update, minimal_update)
    return have_updates
