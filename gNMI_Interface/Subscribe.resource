*** Settings ***
Documentation    Resources specific to gNMI Subscribe operation.
Library          SubscribeLibrary.py  ${LIB_CONFIG}
Resource         gNMIClient.resource


*** Keywords ***

Subscription ${mode} with encoding ${encoding}
    Subscribe    ${mode}    ${encoding}

Device responds
    ${updates}=    Check updates    ${SUBSCRIPTION_TIMEOUT}
    Should be true    ${updates}

Subscribe ONCE with supported encodings
    @{encodings}=    last supported encodings
    FOR    ${encoding}    IN    @{encodings}
        Given subscription ONCE with encoding ${encoding}
        Then device responds
    END

Device capabilities
    Get capabilities from device

Device sends terminated response series and closes the stream
    Device terminates    True

Device sends terminated response series
    Device terminates    False

Device terminates
    [Arguments]    ${should_close}
    ${terminated}=    Check responses terminated    ${should_close}    ${SUBSCRIPTION_TIMEOUT}
    Should be true    ${terminated}    The server did not send sync_response
