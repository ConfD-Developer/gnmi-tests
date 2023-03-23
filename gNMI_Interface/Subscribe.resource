*** Settings ***
Documentation    Resources specific to gNMI Subscribe operation.
Library          SubscribeLibrary.py  ${LIB_CONFIG}
Resource         gNMIClient.resource


*** Keywords ***

Subscribe ${mode} to default path with encoding ${encoding}
    Given subscription paths    ${GET-PATH}
    Then subscribe    ${mode}    ${encoding}
    And close subscription

Subscription ${mode} with encoding ${encoding}
    Subscribe    ${mode}    ${encoding}

Device responds
    Check updates    ${SUBSCRIPTION-TIMEOUT}

Subscribe ONCE with supported encodings
    @{encodings}=    last supported encodings
    FOR    ${encoding}    IN    @{encodings}
        Given subscription ONCE with encoding ${encoding}
        Then device responds
        Close subscription
    END

Device capabilities
    Get capabilities from device

Device sends terminated response series
    Check responses terminated    ${SUBSCRIPTION-TIMEOUT}

Device closes the stream
    Check stream closed    ${SUBSCRIPTION-TIMEOUT}

Subscription STREAM with mode ${stream-mode} with encoding ${encoding}
    Subscribe    STREAM    ${encoding}    ${stream-mode}

Device sends ON_CHANGE updates
    Check on_change updates    ${SUBSCRIPTION-TIMEOUT}
