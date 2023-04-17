*** Settings ***
Documentation    Resources specific to gNMI Subscribe operation.
Resource         gNMIClient.resource


*** Keywords ***

Subscribe ${mode} to default path with default encoding
    Given subscription paths    ${GET-PATH}
    Then subscribe    ${mode}    ${lib_config.default_encoding}
    And close subscription

Subscription ${mode} with encoding ${encoding}
    Subscribe    ${mode}    ${encoding}

Subscription ${mode} with default encoding
    Subscription ${mode} with encoding ${lib_config.default_encoding}

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

Subscription STREAM with mode ${stream-mode} with default encoding
    Subscribe    STREAM    ${lib_config.default_encoding}    ${stream-mode}

Device sends ON_CHANGE updates
    Check on_change updates    ${SUBSCRIPTION-TIMEOUT}    ${SUBSCRIPTION-UPDATE-TIME}

Device sends sample updates
    Check sample updates    ${SAMPLE-PERIOD}    ${SAMPLE-COUNT}    ${SUBSCRIPTION-TIMEOUT}
