*** Settings ***
Documentation    Resources specific to gNMI Subscribe operation.
Resource         gNMIClient.resource


*** Keywords ***
Subscribe ${mode} to default path with default encoding

    [Documentation]    Verify the device does not refuse subscriptions with given mode.
    Given subscription paths    ${GET-PATH}
    Then subscribe    ${mode}    ${lib_config.default_encoding}
    Device responds
    And close subscription

Subscription ${mode} with encoding ${encoding}
    [Documentation]    Start a subscription with given mode and encoding.
    Subscribe    ${mode}    ${encoding}

Subscription ${mode} with default encoding
    [Documentation]    Start a subscription with the device's default encoding.
    Subscription ${mode} with encoding ${lib_config.default_encoding}

Device responds
    [Documentation]    Verify the device sends at least one response.
    Check updates    ${SUBSCRIPTION-TIMEOUT}

Subscribe ONCE with supported encodings
    [Documentation]    For each encoding claimed to be supported by the device, verify
    ...   a subscription can be created and a response is sent.
    [Tags]    robot:continue-on-failure
    @{encodings}=    Last supported encodings
    FOR    ${encoding}    IN    @{encodings}
        Given subscription ONCE with encoding ${encoding}
        Then device responds
        Close subscription
    END

Device capabilities
    [Documentation]    Retrieve device capabilities.
    Get capabilities from device

Device sends terminated response series
    [Documentation]    Verify the device sends a set of responses terminated by
    ...    "sync_response" response.
    Check responses terminated    ${SUBSCRIPTION-TIMEOUT}

Device closes the stream
    [Documentation]    Verify the device closes the response stream.
    Check stream closed    ${SUBSCRIPTION-TIMEOUT}

Streaming subscription with mode ${stream-mode} with default encoding
    [Documentation]    Start a streaming subscription with given stream mode.
    Subscribe    STREAM    ${lib_config.default_encoding}    ${stream-mode}

Device sends ON_CHANGE updates
    [Documentation]    Verify the device keeps sending ON_CHANGE updates for
    ...    ${SUBSCRIPTION-UPDATE-TIME} seconds.
    Check on_change updates    ${SUBSCRIPTION-TIMEOUT}    ${SUBSCRIPTION-UPDATE-TIME}

Device sends sample updates
    [Documentation]    Verify the device sends ${SAMPLE-COUNT} samples within
    ...    ${SAMPLE-PERIOD} seconds.
    Check sample updates    ${SAMPLE-PERIOD}    ${SAMPLE-COUNT}    ${SUBSCRIPTION-TIMEOUT}
