*** Settings ***
Documentation    Resources specific to gNMI ``Get`` RPC/operation.
Library          String
Library          Collections
Resource         gNMIClient.resource
Resource         BasicGet.resource


*** Keywords ***
Iterate root Get with DataType
    [Documentation]    Try sending `GetRequest` with specified DataType parameter value,
    ...                and verify that "ok" response is received.
    [Tags]    type
    [Arguments]    ${type}
    Given DataType set to  ${type}
    When Dispatch Get Request
    Then Should Received Ok Response
    [Teardown]    Teardown gNMI state

Verify root Get with Encoding
    [Documentation]    Try sending `GetRequest` with specified Encoding parameter value,
    ...                and verify that "ok" response is received.
    [Tags]    encoding
    [Arguments]    ${encoding}
    Given Encoding set to  ${encoding}
    When Dispatch Get Request
    Then Should received OK response

Verify Get for Encodings
    [Documentation]    Iterate all the specified encodings, and verify that
    ...                they work for the basic ``GetRequest``.
    [Tags]    encoding  robot:continue-on-failure
    [Arguments]    ${encodings}
    FOR  ${encoding}  IN  @{encodings}
        Verify root Get with Encoding  ${encoding}
    END

Iterate non-empty get path "${path}"
    [Documentation]    Verify that ``GetRequest`` on a configured path pointing to a YANG node
    ...                succeeds and gets non-empty OK response.
    When Verify Get of  ${path}
    Then Check last updates not empty
    [Teardown]    Teardown gNMI state
