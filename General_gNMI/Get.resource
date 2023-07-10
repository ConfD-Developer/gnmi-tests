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

Iterate prefix ${prefix} with path ${path}
    [Documentation]    Retrieve data with prefix + path parameters.
    ...                Verify that response contains some/any data, and is not empty.
    Given Prefix set to  ${prefix}
    And Paths Include  ${path}
    When Dispatch Get Request
    Then Check last updates not empty
    [Teardown]    Teardown gNMI state

Test prefix/path combinations of ${full_path}
    [Documentation]    Iterate splitting of input path into two parts.
    ...                Verify that various combinations of prefix + path work
    ...                for an input path.
    ${steps} =  Count prefix path steps  ${full_path}
    FOR  ${step}  IN RANGE  1  ${steps}
        ${prefix}  ${path} =  Split prefix path  ${full_path}  ${step}
        Iterate prefix ${prefix} with path ${path}
    END

Try getting sanity path
    [Documentation]    Try reading sanity data from path declared by YAML variable "get_sanity_path".
    ...                Fails the test if variable is not set.
    Should Be String    ${get_sanity_path}  Variable "get_sanity_path" has to be string (XPath).
    When Verify Get of  ${get_sanity_path}
    Then Check last updates not empty
