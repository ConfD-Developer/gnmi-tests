*** Settings ***
Documentation   A gNMI OpenConfig-specific subscription test suite.
Test Tags       OpenConfig  subscribe
Resource        OcSubscribe.resource
Library         OcSubscribeLibrary.py  ${LIB_CONFIG}
Test Setup      Setup gNMI Client
Test Teardown   Close client


*** Test Cases ***

Test ON_CHANGE streaming subscriptions on interfaces
    [Documentation]    Verify that the expected interface paths are all covered by the initial
    ...    set of updates and that on-change streaming sends updates on those paths.
    Given expected paths     ${OC-INTERFACE-PATHS}
    And subscription STREAM with mode ON_CHANGE with default encoding
    Then verify expected paths
