*** Settings ***
Documentation    Keywords specific to OpenConfig Subscribe tests.
Resource         ../gNMI_Interface/Subscribe.resource


*** Keywords ***
Verify expected paths
    Check expected paths    ${SUBSCRIPTION-TIMEOUT}    ${SUBSCRIPTION-UPDATE-TIME}
    
