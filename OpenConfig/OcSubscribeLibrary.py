from __future__ import annotations

import typing as t
import json

from SubscribeLibrary import SubscribeLibrary
from gnmi_config import GNMIConfig, GNMIConfigValue, GNMIConfigTree, GNMIConfigList, \
    apply_response, UpdateType

from robot.api.logger import trace


class OcSubscribeLibrary(SubscribeLibrary):
    def expected_paths(self, pathdict: dict[str, list[str]]) -> None:
        self._expected_paths = pathdict
        self.subscription_paths(*pathdict.keys())

    def check_expected_paths(self, timeout: int, update_time: int) -> None:
        config = GNMIConfigTree()
        expected = PathTree(self._expected_paths)
        for response in self._iterate_initial_responses(timeout):
            apply_response(config, response, UpdateType.STRUCTURE)
        expected.check_covered_by(config)
        if expected.omissions:
            elems = ', '.join(list(expected.omissions)[:10])
            if len(expected.omissions) > 10:
                elems += ', ...'
            raise AssertionError(f'Elements not covered by initial updates: {elems}')
        self._wait_on_change_updates(config, timeout, update_time)


class PathTree:
    def __init__(self, expected_paths: dict[str, list[str]]):
        self._expected_paths = expected_paths
        self.omissions = set()

    def check_covered_by(self, config: GNMIConfigTree) -> None:
        for base_path, subpaths in self._expected_paths.items():
            trace(f'testing {base_path}')
            for instance in self.lookup_instances(base_path.split('/')[1:], config):
                for subpath in subpaths:
                    trace(f'verify {subpath} on {instance}')
                    for leaf in self.lookup_instances(subpath.split('/'), instance):
                        # make sure we go through all of them
                        pass

    def lookup_instances(self, path_elems: list[str], config: GNMIConfig) \
            -> t.Iterable[GNMIConfig]:
        if not path_elems:
            yield config
            return
        elem = path_elems[0]
        if isinstance(config, GNMIConfigTree):
            if elem not in config.tree:
                self.omissions.add(elem)
            else:
                yield from self.lookup_instances(path_elems[1:], config.tree[elem])
        elif isinstance(config, GNMIConfigList):
            for key, instance in config.instances.items():
                yield from self.lookup_instances(path_elems, instance)
        elif isinstance(config, GNMIConfigValue):
            # may happen for aggregated JSON_IETF
            if not config.value.HasField('json_ietf_val'):
                self.omissions.add(elem)
                return
            ctree = json.loads(config.value.json_ietf_val)
            for elem in path_elems:
                # no lists allowed...
                if elem not in ctree:
                    self.omissions.add(elem)
                    break
                ctree = ctree[elem]
        else:
            raise RuntimeError(f'path error: {path_elems}')
