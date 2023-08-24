*** Settings ***
Documentation    Generic device agnostic test suite for gNMI ``Subscribe`` RPC/operation.
Test Tags        subscribe

Resource         Subscribe.resource
Library          SubscribeLibrary.py  ${LIB_CONFIG}

Resource         gNMIClient.resource
Test Setup       Setup gNMI Client
Test Teardown    Close client


*** Test Cases ***
Basic subscription with "mode" parameter
    [Tags]    sanity
    [Documentation]    Test that the device correctly responds to all three
    ...    "Subscribe" request modes.    No further functionality (such as actually
    ...    polling the device) is tested.
    [Template]    Subscribe ${mode} to default path with default encoding
    STREAM
    ONCE
    POLL

Subscribe ONCE with supported "encoding" values
    [Tags]    sanity
    [Documentation]    Verify that the device is able to respond correctly for
    ...    all declared encodings.
    Given device capabilities
    And subscription paths    ${GET-PATH}
    Then subscribe ONCE with supported encodings

Subscribe ONCE does not aggregate by deault
    [Tags]    sanity
    [Documentation]    Verify that the device is able to respond correctly for
    ...    all declared encodings. Verify the data is not aggregated.
    Given device capabilities
    And subscription paths    ${GET-PATH}
    Then subscribe ONCE does not aggregate by default

Two subscriptions in single request with the same "path"
    [Documentation]    Verify that the device can handle ONCE subscription
    ...    with two identical paths.
    Given subscription paths    ${GET-PATH}    ${GET-PATH}
    And subscription ONCE with default encoding
    Then device responds

Two subscriptions in single request with different "path"
    [Documentation]    Verify that the device can handle ONCE subscription
    ...    with two different paths.
    Given subscription paths    ${GET-PATH}    ${SECONDARY-PATH}
    And subscription ONCE with default encoding
    Then device responds

Subscribe ONCE sends final message with "sync_response"
    [Documentation]    When a ONCE subscription is created, the device must
    ...    respond with a series of responses terminated by an empty
    ...    response with "sync_response".
    Given Subscription paths    ${GET-PATH}
    And Subscription ONCE with default encoding
    Then Device sends terminated response series
    And Device closes the stream

Subscribe POLL sends final message with "sync_response"
    [Documentation]    When a POLL subscription is created, the device must
    ...    send an initial set of responses terminated by an empty
    ...    response with "sync_response".
    Given Subscription paths    ${GET-PATH}
    And Subscription POLL with default encoding
    Then Device sends terminated response series

Subscribe STREAM sends final message with "sync_response"
    [Documentation]    When a STREAM subscription is created, the device must
    ...    send an initial set of responses terminated by an empty
    ...    response with "sync_response".
    Given Subscription paths    ${GET-PATH}
    And Subscription STREAM with default encoding
    Then Device sends terminated response series

STREAM with ON_CHANGE mode
    [Documentation]    ON_CHANGE subscriber expects to receive the initial set
    ...    of responses and then, within a timeout, an updated leaf.
    Given Subscription paths    ${SUBSCRIPTION-STREAM-PATH}
    And streaming subscription with mode ON_CHANGE with default encoding
    Then device sends ON_CHANGE updates

STREAM with SAMPLE mode
    [Documentation]    SAMPLE subscriber expects the initial set of responses
    ...    and then samples over a configured number of intervals.
    Given Subscription paths    ${SUBSCRIPTION-STREAM-PATH}
    And Streaming subscription with mode SAMPLE with default encoding
    Then Device sends SAMPLE updates

STREAM with SAMPLE mode without redundancies
    [Documentation]    This test verifies that the device sends periodic updates,
    ...    the initial sample covers complete set of nodes, and following samples
    ...    are without redundancies.
    [Tags]    unimplemented
    Skip
