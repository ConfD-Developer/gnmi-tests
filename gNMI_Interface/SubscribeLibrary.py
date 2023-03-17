from __future__ import annotations

import typing as t

from confd_gnmi_common import make_gnmi_path, encoding_str_to_int
from confd_gnmi_client import ConfDgNMIClient
from CapabilitiesLibrary import CapabilitiesLibrary

import gnmi_pb2 as gnmi

import threading
import queue

SlistType = t.Optional[t.Union[gnmi.Poll, gnmi.SubscriptionList]]


class Requester(threading.Thread):
    def __init__(self, client: ConfDgNMIClient) -> None:
        self.client: ConfDgNMIClient = client
        self.slist_queue: queue.Queue[SlistType] = queue.Queue()
        self.response_queue: queue.Queue[gnmi.SubscribeResponse] = queue.Queue()
        super().__init__()

    def run(self) -> None:
        # TODO: this dumps the MultiThreaded thing exception for XR
        for response in self.client.subscribe(self.requests()):
            self.response_queue.put(response)
        self.response_queue.put(None)

    def requests(self) -> t.Iterator[gnmi.SubscribeRequest]:
        while (slitem := self.slist_queue.get()) is not None:
            if isinstance(slitem, gnmi.SubscriptionList):
                yield gnmi.SubscribeRequest(subscribe=slitem)
            elif isinstance(slitem, gnmi.Poll):
                yield gnmi.SubscribeRequest(poll=slitem)

    def enqueue(self, item: SlistType) -> None:
        self.slist_queue.put(item)

    def responses(self, timeout: int) -> t.Iterator[gnmi.SubscribeResponse]:
        while (response := self.response_queue.get(timeout=timeout)) is not None:
            yield response


class SubscribeLibrary(CapabilitiesLibrary):
    "ROBOT test suite library for servicing the gNMI SubscribeRequest tests."
    ROBOT_LIBRARY_SCOPE = 'SUITE'

    def __init__(self, extra_logs: bool = False) -> None:
        super().__init__(extra_logs)
        self.paths: t.List[str] = []
        self.requester: t.Optional[Requester] = None

    def close_client(self) -> None:
        self.paths = []
        if self.requester is not None:
            self.requester.enqueue(None)
            self.requester.join(2)
        self.requester = None
        super().close_client()

    def subscribe(self, mode: str, encoding: str) -> None:
        paths = [make_gnmi_path(path) for path in self.paths]
        iencoding = encoding_str_to_int(encoding)
        slist = ConfDgNMIClient.make_subscription_list(make_gnmi_path(''), paths, mode, iencoding)
        self.requester = Requester(self._client)
        self.requester.start()
        self.requester.enqueue(slist)

    def check_updates(self, timeout: int) -> bool:
        # return the first notification update in the first nonempty response
        try:
            next(update
                 for response in self.requester.responses(timeout)
                 for update in response.update.update)
            return True
        except StopIteration:
            return False

    def subscription_paths(self, *paths: str) -> None:
        self.paths = paths

    def check_responses_terminated(self, should_close: bool, timeout: int) -> bool:
        terminated = False
        try:
            for response in self.requester.responses(timeout):
                assert not terminated, 'The server did not close the stream'
                if response.sync_response:
                    terminated = True
                    if not should_close:
                        # the stream does not need to be closed, exit now
                        break
        except queue.Empty:
            if terminated:
                raise AssertionError('The server did not close the stream')
            else:
                raise AssertionError('The server did not send sync_response')
        return terminated
