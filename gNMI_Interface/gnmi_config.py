"""Utility classes for representation of gNMI device configuration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
import typing as t
import json

from confd_gnmi_common import add_path_prefix, make_formatted_path

import gnmi_pb2 as gnmi


UpIxT = t.TypeVar('UpIxT', bound='UpdateIndex')
ConfT = t.TypeVar('ConfT', bound='GNMIConfig')


class UpdateType(Enum):
    '''Type of configuration tree update.

    Three instances are supported:

    - NONE - no update at all
    - VALUE - only a value has been updated
    - STRUCTURE - a new leaf or a full subtree has been created
    '''
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


def assert_config(config: GNMIConfig, clazz: t.Type[ConfT]) -> ConfT:
    assert isinstance(config, clazz), \
        f'expected config update {clazz.type}, received {config.type}'
    return config


class GNMIConfig(ABC, t.Generic[UpIxT]):
    '''Configuration tree representation.'''
    type: t.Optional[str] = None

    @abstractmethod
    def update(self, UpIxT) -> UpdateType: ...

    @abstractmethod
    def __repr__(self) -> str: ...

    @abstractmethod
    def covered_by(self, other: GNMIConfig) -> bool:
        '''Verify that this configuration is covered by the other configuration.

        A configuration tree is covered if the other configuration
        contains at least the same instances of containers/lists/etc,
        not necessarily the same values.
        '''
        ...


class UpdateIndex(ABC, t.Generic[UpIxT]):
    '''A pointer into a update data, either a path and value or a JSON tree.

    An update from a gNMI server consists of a path and a value.  The
    update needs to be applied to the current configuration tree and
    instances of this class serve as pointers into the path or into
    the value while gradually applying them.
    '''
    @abstractmethod
    def config_class(self) -> t.Type[GNMIConfig[UpIxT]]: ...

    @abstractmethod
    def new_child(self) -> GNMIConfig[UpIxT]: ...

    def rectify_config_type(self, config: GNMIConfig) -> GNMIConfig[UpIxT]:
        return assert_config(config, self.config_class())


TreeIndexT = t.Union['PathTreeIndex', 'JsonTreeIndex']


class GNMIConfigTree(GNMIConfig[TreeIndexT]):
    '''Configuration tree instance.'''
    type = 'tree'

    def __init__(self) -> None:
        self.tree: t.Dict[str, GNMIConfig] = {}

    def __repr__(self):
        return f'{self.tree}'

    def update(self, ix: TreeIndexT) -> UpdateType:
        utype = UpdateType.NONE
        for elname, subix in ix.subindices():
            if elname in self.tree:
                child = subix.rectify_config_type(self.tree[elname])
            else:
                child = subix.new_child()
                self.tree[elname] = child
                utype = UpdateType.STRUCTURE
            utype += child.update(subix)
        return utype

    def covered_by(self, other: GNMIConfig[TreeIndexT]) -> bool:
        config = assert_config(other, GNMIConfigTree)
        return not self.tree.keys() - config.tree.keys() \
            and all(sub.covered_by(config.tree[elm]) for elm, sub in self.tree.items())


class GNMIConfigList(GNMIConfig['PathListIndex']):
    '''Representation of a list configuration.'''
    type = 'list'

    def __init__(self, initial_keyset: t.Dict[str, str]) -> None:
        self.keys: t.Tuple[str, ...] = tuple(initial_keyset.keys())
        self.instances: t.Dict[t.Tuple[str, ...], GNMIConfig] = {}

    def __repr__(self):
        pairs = ', '.join(f'{t} -> {v}' for t, v in self.instances.items())
        return f'[{pairs}]'

    def update(self, ix: PathListIndex) -> UpdateType:
        subix = ix.subindex()
        keyvals = ix.key_values()
        if keyvals in self.instances:
            child = subix.rectify_config_type(self.instances[keyvals])
            utype = UpdateType.NONE
        else:
            child = subix.new_child()
            self.instances[keyvals] = child
            utype = UpdateType.STRUCTURE
        return child.update(subix) + utype

    def covered_by(self, other: GNMIConfig[PathListIndex]) -> bool:
        config = assert_config(other, GNMIConfigList)
        return not self.instances.keys() - config.instances.keys() \
            and all(sub.covered_by(config.instances[key]) for key, sub in self.instances.items())


ValueIndexT = t.Union['JsonValueIndex', 'PlainValueIndex']


class GNMIConfigValue(GNMIConfig[ValueIndexT]):
    '''Plain value configuration.'''
    type = 'value'

    def __init__(self) -> None:
        self.value: gnmi.TypedValue = gnmi.TypedValue()

    def __repr__(self):
        return repr(self.value)

    def update(self, ix: ValueIndexT) -> UpdateType:
        if ix.value == self.value:
            return UpdateType.NONE
        self.value = ix.value
        return UpdateType.VALUE

    def covered_by(self, other: GNMIConfig[ValueIndexT]) -> bool:
        assert_config(other, GNMIConfigValue)
        return True


class PathIndex(UpdateIndex[UpIxT]):
    '''Pointer into a gNMI path with the value'''
    def __init__(self, elems: t.List[gnmi.PathElem], index: int, value: gnmi.TypedValue) -> None:
        self.elems = elems
        self.index = index
        self.value = value
        self.elem = elems[index]


class PathTreeIndex(PathIndex['PathTreeIndex']):
    '''Pointer into a gNMI path at a point that corresponds to a tree (i.e. a container).'''
    def config_class(self):
        return GNMIConfigTree

    def subindices(self) -> t.Iterable[t.Tuple[str, UpdateIndex]]:
        elem = self.elems[self.index]
        if elem.key:
            yield elem.name, PathListIndex(self.elems, self.index, self.value)
        elif self.index + 1 == len(self.elems):
            yield elem.name, new_value_index(self.value)
        else:
            yield elem.name, PathTreeIndex(self.elems, self.index + 1, self.value)

    def new_child(self):
        return GNMIConfigTree()


class PathListIndex(PathIndex['PathListIndex']):
    '''Pointer into a gNMI path that corresponds to a list.'''
    def config_class(self):
        return GNMIConfigList

    def subindex(self) -> UpdateIndex:
        if self.index + 1 == len(self.elems):
            return new_value_index(self.value)
        else:
            return PathTreeIndex(self.elems, self.index + 1, self.value)

    def new_child(self):
        return GNMIConfigList(self.elem.key)

    def key_values(self) -> t.Tuple[str, ...]:
        return tuple(v for _k, v in self.elem.key.items())


JsonPrimitiveT = t.Union[int, str, float]
JsonValueT = t.Union[JsonPrimitiveT, t.Dict[str, 'JsonValueT']]


def new_value_index(value: gnmi.TypedValue) \
        -> t.Union[PlainValueIndex, JsonTreeIndex, JsonValueIndex]:
    '''Create a new index from a value - either plain value or a JSON thing.'''
    if value.HasField('json_ietf_val'):
        return new_json_index(json.loads(value.json_ietf_val))
    else:
        # can ListFields() be empty, is it TypedValue?
        return PlainValueIndex(value.ListFields()[0][1])


def new_json_index(value: JsonValueT) -> t.Union[JsonTreeIndex, JsonValueIndex]:
    '''Create new JSON-based index.'''
    if isinstance(value, dict):
        return JsonTreeIndex(value)
    else:
        return JsonValueIndex(value)


class JsonValueIndex(UpdateIndex['JsonValueIndex']):
    '''Pointer at a JSON tree leaf.'''
    def __init__(self, value: JsonPrimitiveT) -> None:
        self.value = value

    def config_class(self):
        return GNMIConfigValue

    def new_child(self):
        return GNMIConfigValue()


class PlainValueIndex(UpdateIndex['PlainValueIndex']):
    '''Plain value "index".'''
    def __init__(self, value: t.Any) -> None:
        self.value = value

    def config_class(self):
        return GNMIConfigValue

    def new_child(self):
        return GNMIConfigValue()


class JsonTreeIndex(UpdateIndex['JsonTreeIndex']):
    '''Pointer into a JSON tree.'''
    def __init__(self, value: dict) -> None:
        self.value = value

    def config_class(self):
        return GNMIConfigTree

    def subindices(self) -> t.Iterable[t.Tuple[str, UpdateIndex]]:
        for name, val in self.value.items():
            yield name, new_json_index(val)

    def new_child(self):
        return GNMIConfigTree()


def apply_update(config: GNMIConfig, path: gnmi.Path, update: gnmi.Update,
                 minimal_update: UpdateType) -> None:
    '''Apply a gNMI Update instance and verify that satisfies the minimal update requirement.'''
    if not minimal_update <= config.update(PathTreeIndex(path.elem, 0, update.val)):
        up_str = f'{make_formatted_path(path)} = {update.val}'
        if minimal_update == UpdateType.STRUCTURE:
            msg = f'expected structural update, received: {up_str}'
        else:
            msg = f'received non-update: {up_str}'
        raise AssertionError(msg)


def apply_response(config: GNMIConfig, response: gnmi.SubscribeResponse,
                   minimal_update: UpdateType = UpdateType.NONE) -> bool:
    '''Apply a full gNMI SubscribeResponse instance verifying the
    individual updates satisfy minimal update requirements.'''
    notif = response.update
    have_updates = False
    for update in notif.update:
        have_updates = True
        path = add_path_prefix(update.path, notif.prefix)
        apply_update(config, path, update, minimal_update)
    return have_updates
