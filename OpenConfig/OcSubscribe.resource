*** Settings ***
Documentation    Keywords specific to OpenConfig Subscribe tests.
Resource         ../General_gNMI/Subscribe.resource


*** Keywords ***
Verify expected paths
    [Documentation]    Verify that the device sends the initial subscription snapshot
    ...    covering the expected paths and that the device keeps sending updates for
    ...    given time.
    Check Expected Paths    ${SUBSCRIPTION-TIMEOUT}    ${SUBSCRIPTION-UPDATE-TIME}
