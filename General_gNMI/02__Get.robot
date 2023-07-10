*** Settings ***
Documentation    Generic device agnostic test suite for gNMI ``Get`` RPC/operation.
Test Tags        get

Library          Collections
Library          GetLibrary.py  ${LIB_CONFIG}

Resource         Get.resource
Resource         gNMIClient.resource

Suite Setup      Setup gNMI Client
Suite Teardown   Close gNMI Client
Test Teardown    Teardown gNMI state


*** Test Cases ***
Sanity check for device defined path
    [Documentation]    Make sanity request to a "path" on device guaranteed to return some/any data.
    [Tags]    sanity
    Try getting sanity path

Parameter "path" set for root - all data
    [Documentation]    Try a request with "path" param set to '/',
    ...                ignoring the actual payload returned.
    ...                This may be a costly operation depending on device feature/model set.
    [Tags]    path  costly
    Given Paths include  /
    When Dispatch Get Request
    Then Should Received Ok Response

Parameter "prefix" on root path
    [Documentation]    Try getting whole config by setting ``prefix=/`` parameter.
    ...                Check that OK response is received without any internal data verification.
    [Tags]    prefix    costly
    Given Prefix set to  /
    When Dispatch Get Request
    Then Should received OK Response

Parameter "prefix" with "path" combination
    [Documentation]    Test the nested data path, declared by variable `get_prefix_path` in device YAML file.
    ...                Split the path into various combinations of prefix + path parameters of GetRequest.
    [Tags]  prefix  path
    Test prefix/path combinations of ${get_prefix_path}

Parameter "type" - valid values return OK response
    [Documentation]    Check that all the possible ``DataType`` values can be used
    ...                as "type" parameter of ``GetRequest``
    ...                (while not setting any other request parameters).
    ...
    ...                Test succeeds when "OK" response with any data is received from server.
    [Template]         Iterate root Get with DataType
    ALL
    CONFIG
    STATE
    OPERATIONAL

Parameter "type" - an unsupported value returns Error response
    [Documentation]    Check that setting an invalid value (other than all the standard
    ...                specified ones for ``DataType`` value for ``GetRequest``
    ...                results in error response from server.
    [Tags]    type  negative
    Given DataType set to  INVALID
    When Dispatch Get Request
    Then Should Received Error Response

Parameter "encoding" - supported values get OK response
    [Documentation]    Check which encodings server advertises as supported via ``CapabilityRequest``.
    ...
    ...                Verify that all of them can be used as "encoding" parameter of ``GetRequest``
    ...                (while not setting any other request parameters).
    ...
    ...                Test succeeds when "OK" response with any data is received from server
    ...                for all of the advertised encodings.
    [Tags]    encoding
    When Get Capabilities From Device
    Then Should Received Ok Response

    @{supported}=  Last Supported Encodings
    Then Should Not Be Empty  ${supported}
    And Verify Get for Encodings  ${supported}

Parameter "encoding" - unsupported value gets Error response
    [Documentation]    Check which encodings server does NOT "advertise" as supported.
    ...                Verify that all of them, when used as "encoding" parameter of ``GetRequest``
    ...                (while not setting any other request parameters),
    ...                return erroneous response from server.
    [Tags]    negative  encoding  robot:continue-on-failure
    When Get Capabilities From Device
    Then Should Received Ok Response

    @{unsupported}=    Last Unsupported Encodings
    FOR    ${encoding}    IN    @{unsupported}
        Given Encoding set to  ${encoding}
        When Dispatch Get Request
        Then Should received Error response
    END

Parameter "encoding" - invalid value gets Error response
    [Documentation]    Try a ``GetRequest`` with invalid encoding value
    ...                (while not setting any other request parameters),
    ...                and verify that server returns an erroneous response.
    [Tags]    negative  encoding
    Given Encoding set to  'invalid'
    When Dispatch Get Request
    Then Should received Error Response

# Non-existing ModelData
#     [Tags]    use_models
#     Verify Get of model  non-existing-model  Should received Error response

# Iterate all ModelData one by one
# TODO - device might have tons of models, need some filter...
# TODO - set "use-models" param instead of path!
#     [Tags]    costly  use_models
#     ${model_names}=  Get supported model names
#     ${model_count}=  Get Length  ${model_names}
#     Log  Received ${model_count} model names from device. Starting to iterate:
#     Verify Get for models  ${model_names}

Get configured paths
    [Documentation]    Verify that generic request for an XPaths declared in config file
    ...                can be issued against server, and that non-empty OK response with
    ...                some data is received.
    [Tags]    path
    [Template]    Iterate non-empty get path "${path}"
    FOR  ${path}  IN  @{GNMI_GET_PATHS}
        ${path}
    END
