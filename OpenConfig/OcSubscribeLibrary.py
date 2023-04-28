from __future__ import annotations

import typing as t
import json

from SubscribeLibrary import SubscribeLibrary
from gnmi_config import GNMIConfig, GNMIConfigValue, GNMIConfigTree, GNMIConfigList, \
    apply_response, UpdateType

from robot.api.logger import trace

MAX_REPORTED_OMISSIONS = 10


class OcSubscribeLibrary(SubscribeLibrary):
    def expected_paths(self, pathdict: dict[str, list[str]]) -> None:
        '''Expected paths is a dictionary mapping from a base path to
        a list of "expected subpaths".'''
        self._expected_paths = pathdict
        self.subscription_paths(*pathdict.keys())

    def check_expected_paths(self, timeout: int, update_time: int) -> None:
        '''Go over responses and build a configuration tree.

        It is expected that the initial responses are all "STRUCTURE"
        updates, and also that the tree after the initial responses
        are done covers all expected paths.  The following updates can
        be "VALUE" updates only.
        '''
        config = GNMIConfigTree()
        expected = PathTree(self._expected_paths)
        for response in self._iterate_initial_responses(timeout):
            apply_response(config, response, UpdateType.STRUCTURE)
        expected.check_covered_by(config)
        if expected.omissions:
            elems = ', '.join(list(expected.omissions)[:MAX_REPORTED_OMISSIONS])
            if len(expected.omissions) > MAX_REPORTED_OMISSIONS:
                elems += f', ... (in total {len(expected.omissions)} elements missing)'
            raise AssertionError(f'Elements not covered by initial updates: {elems}')
        self._wait_on_change_updates(config, timeout, update_time)


class PathTree:
    def __init__(self, expected_paths: dict[str, list[str]]):
        self._expected_paths = expected_paths
        self.omissions = set()

    def check_covered_by(self, config: GNMIConfigTree) -> None:
        '''Check that the tree consisting of expected paths is covered by the configuration tree.'''
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
        '''For given path and a configuation tree yield all instances
        of the path that appear in the configuration.

        The path and the configuration are assumed to be rooted at the
        same node (root or inside the model tree).  If the path
        targets a list or crosses boundary of a list, the function
        looks up all instances of that list that are part of the
        configuration.  If given path element does not appear in the
        tree, it is added to the `omissions` list.
        '''
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
