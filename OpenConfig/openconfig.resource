*** Settings ***
Documentation    Resources specific to OpenConfig telemetry testing.
Library          ../General_gNMI/GetLibrary.py  ${LIB_CONFIG}
Resource    ../General_gNMI/gNMIClient.resource


*** Keywords ***
Iterate path "${path}" with DataType ${type}
    [Documentation]    Retrieve data from the specified path having set the specified ``GetRequests``'s ``type``,
    ...
    ...                Cleanup the gNMI library state after to allow other clean iterations.
    Given Paths include  ${path}
    and DataType set to  ${type}
    When Dispatch Get Request
    Then Should Received Ok Response
    [Teardown]    Teardown gNMI state
