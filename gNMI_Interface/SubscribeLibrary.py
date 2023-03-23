from __future__ import annotations

from abc import ABC, abstractmethod
import typing as t
import threading
import queue

from confd_gnmi_common import make_gnmi_path, encoding_str_to_int, add_path_prefix
from confd_gnmi_client import ConfDgNMIClient
from CapabilitiesLibrary import CapabilitiesLibrary

import grpc
import gnmi_pb2 as gnmi

SlistType = t.Optional[t.Union[gnmi.Poll, gnmi.SubscriptionList]]


class Requester(threading.Thread):
    def __init__(self, client: ConfDgNMIClient) -> None:
        super().__init__()
        self.client: ConfDgNMIClient = client
        self._slist_queue: queue.Queue[SlistType] = queue.Queue()
        self._response_queue: queue.Queue[gnmi.SubscribeResponse] = queue.Queue()
        self._responses: t.Optional[gnmi.SubscribeResponse] = None

    def run(self) -> None:
        self._responses = self.client.subscribe(self.requests())
        try:
            for response in self._responses:
                self._response_queue.put(response)
        except grpc.RpcError as err:
            if isinstance(err, grpc.Call) and err.code() == grpc.StatusCode.CANCELLED:
                # cancelled locally
                pass
            elif isinstance(err, grpc.Call) and 'EOF' in err.details():
                # some devices throw this when the request stream is closed
                pass
            else:
                raise
        finally:
            self._response_queue.put(None)

    def requests(self) -> t.Iterator[gnmi.SubscribeRequest]:
        while (slitem := self._slist_queue.get()) is not None:
            if isinstance(slitem, gnmi.SubscriptionList):
                yield gnmi.SubscribeRequest(subscribe=slitem)
            elif isinstance(slitem, gnmi.Poll):
                yield gnmi.SubscribeRequest(poll=slitem)
        if self._responses is not None:
            self._responses.cancel()

    def enqueue(self, item: SlistType) -> None:
        self._slist_queue.put(item)

    def responses(self, timeout: int) -> t.Iterator[gnmi.SubscribeResponse]:
        if not self.is_alive():
            # yield only queued updates
            for _ in range(self._response_queue.qsize()):
                if (response := self._response_queue.get()) is None:
                    return
                yield response
        else:
            while (response := self._response_queue.get(timeout=timeout)) is not None:
                yield response
            self.join()


class SubscribeLibrary(CapabilitiesLibrary):
    "ROBOT test suite library for servicing the gNMI SubscribeRequest tests."
    ROBOT_LIBRARY_SCOPE = 'SUITE'

    def __init__(self, extra_logs: bool = False) -> None:
        super().__init__(extra_logs)
        self.paths: t.Tuple[str, ...] = ()
        self.requester: t.Optional[Requester] = None

    def close_client(self) -> None:
        self.paths = ()
        self.close_subscription()
        super().close_client()

    def close_subscription(self) -> None:
        if self.requester is not None:
            self.requester.enqueue(None)
            self.requester.join(2)
        self.requester = None

    def subscribe(self, mode: str, encoding: str, stream_mode: t.Optional[str] = None) -> None:
        paths = [make_gnmi_path(path) for path in self.paths]
        iencoding = encoding_str_to_int(encoding)
        prefix = make_gnmi_path('')
        if mode == 'STREAM' and stream_mode is not None:
            slist = ConfDgNMIClient.make_subscription_list(prefix, paths, mode,
                                                           iencoding, stream_mode)
        else:
            slist = ConfDgNMIClient.make_subscription_list(prefix, paths, mode, iencoding)
        self.requester = Requester(self._client)
        self.requester.start()
        self.requester.enqueue(slist)

    def check_updates(self, timeout: int) -> None:
        # Check if there is a nonempty notification update
        try:
            next(update
                 for response in self.requester.responses(timeout)
                 for update in response.update.update)
        except StopIteration:
            raise AssertionError('The server did not send any updates')

    def subscription_paths(self, *paths: str) -> None:
        self.paths = paths

    def check_responses_terminated(self, timeout: int) -> None:
        for rsp in self._iterate_initial_responses(timeout):
            pass

    def _iterate_initial_responses(self, timeout: int) -> t.Iterator[gnmi.SubscribeResponse]:
        try:
            for response in self.requester.responses(timeout):
                if response.sync_response:
                    return
                yield response
        except queue.Empty:
            pass
        raise AssertionError('The server did not send sync_response')

    def check_stream_closed(self, timeout: int) -> None:
        NOT_CLOSED = 'The server did not close the stream'
        try:
            next(self.requester.responses(timeout))
            # there still was something in the stream
            raise AssertionError(NOT_CLOSED)
        except StopIteration:
            # this is ok
            return
        except queue.Empty:
            # caused by timeout - the stream has not been closed
            raise AssertionError(NOT_CLOSED)

    def check_on_change_updates(self, timeout: int) -> None:
        configs = GNMIConfigTree()
        for response in self._iterate_initial_responses(timeout):
            notif = response.update
            for update in notif.update:
                path = add_path_prefix(notif.prefix, update.path)
                configs.update(path.elem, 0, update.val)
        responses = False
        for response in self.requester.responses(timeout):
            notif = response.update
            for update in notif.update:
                responses = True
                path = add_path_prefix(notif.prefix, update.path)
                assert configs.update(path.elem, 0, update.val), 'received a non-update'
        assert responses, 'no updates were received'


class GNMIConfig(ABC):
    @abstractmethod
    def update(self, elems: t.List[gnmi.PathElem], index: int, value: gnmi.TypedValue) -> bool: ...


class GNMIConfigTree(GNMIConfig):
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

    def update(self, elems: t.List[gnmi.PathElem], index: int, value: gnmi.TypedValue) -> bool:
        assert index < len(elems)
        elem = elems[index]
        if elem.name in self.tree:
            child = self.tree[elem.name]
        else:
            child = self.new_child(elems, index)
            self.tree[elem.name] = child
        return child.update(elems, index + 1, value)


class GNMIConfigList(GNMIConfig):
    def __init__(self, initial_keyset: t.Dict[str, str]) -> None:
        self.keys: t.Tuple[str, ...] = tuple(initial_keyset.keys())
        self.instances: t.Dict[t.Tuple[str, ...], GNMIConfig] = {}

    def update(self, elems: t.List[gnmi.PathElem], index: int, value: gnmi.TypedValue) -> bool:
        assert 0 < index
        assert elems[index-1].key
        keyvals: t.Tuple[str, ...] = tuple(elems[index-1].key[k] for k in self.keys)
        if keyvals in self.instances:
            child = self.instances[keyvals]
        else:
            if index == len(elems):
                child = GNMIConfigValue()
            else:
                child = GNMIConfigTree()
            self.instances[keyvals] = child
        return child.update(elems, index, value)


class GNMIConfigValue(GNMIConfig):
    def __init__(self) -> None:
        self.value: gnmi.TypedValue = gnmi.TypedValue()

    def update(self, elems: t.List[gnmi.PathElem], index: int, value: gnmi.TypedValue) -> bool:
        assert index == len(elems)
        if self.value == value:
            return False
        self.value = value
        return True
