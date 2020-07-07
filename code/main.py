import os
import json
import time
from json import JSONDecodeError
from utils import AMLConfigurationException, ActionDeploymentError, CredentialsVerificationError, ResourceManagementError, required_parameters_provided, mask_parameter, get_template_parameters, get_deploy_mode_obj
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import DeploymentMode

def main():
    # # Loading input values
    # print("::debug::Loading input values")
    template_file = os.environ.get("INPUT_ARMTEMPLATE_FILE", default="arm_deploy.json")
    template_params_file = os.environ.get("INPUT_ARMTEMPLATEPARAMS_FILE", default="")
    azure_credentials = os.environ.get("INPUT_AZURE_CREDENTIALS", default="{}")
    resource_group = os.environ.get("INPUT_RESOURCE_GROUP", default=None)
    mapped_params = os.environ.get("INPUT_MAPPED_PARAMS", default="{}")
    deployment_mode=os.environ.get("INPUT_DEPLOYMENT_MODE", default="Incremental")
    
    deploy_enum=get_deploy_mode_obj(deployment_mode)
    try:
        azure_credentials = json.loads(azure_credentials)
    except JSONDecodeError:
        print("::error::Please paste output of `az ad sp create-for-rbac --name <your-sp-name> --role contributor --scopes /subscriptions/<your-subscriptionId>/resourceGroups/<your-rg> --sdk-auth` as value of secret variable: AZURE_CREDENTIALS")
        raise AMLConfigurationException(f"Incorrect or poorly formed output from azure credentials saved in AZURE_CREDENTIALS secret. See setup in https://github.com/Azure/aml-workspace/blob/master/README.md")

    try:
        mapped_params = json.loads(mapped_params)
    except JSONDecodeError:
        print("::error::Incorrect mapped parameters Format , please put mapped parameters strings like this {\"patToken\":\"${{secrets.PAT_TOKEN}}\", .... }")
        raise AMLConfigurationException(f"Incorrect or poorly formed mapped params. See setup in https://github.com/Azure/aml_configure/blob/master/README.md")

    if not resource_group:
        raise AMLConfigurationException(f"A resource group must be provided")
    # Checking provided parameters
    print("::debug::Checking provided parameters")
    required_parameters_provided(
        parameters=azure_credentials,
        keys=["tenantId", "clientId", "clientSecret"],
        message="Required parameter(s) not found in your azure credentials saved in AZURE_CREDENTIALS secret for logging in to the workspace. Please provide a value for the following key(s): "
    )

    # # Loading parameters file
    # print("::debug::Loading parameters file")
    template_file_file_path = os.path.join(".cloud", ".azure", template_file)
    
    # Mask values
    print("::debug::Masking parameters")
    mask_parameter(parameter=azure_credentials.get("tenantId", ""))
    mask_parameter(parameter=azure_credentials.get("clientId", ""))
    mask_parameter(parameter=azure_credentials.get("clientSecret", ""))
    #mask_parameter(parameter=azure_credentials.get("subscriptionId", ""))
    
    # Login User on CLI
    tenant_id=azure_credentials.get("tenantId", "")
    service_principal_id=azure_credentials.get("clientId", "")
    service_principal_password=azure_credentials.get("clientSecret", "")
    subscriptionId=azure_credentials.get("subscriptionId", "")
    
    parameters=get_template_parameters(template_params_file,mapped_params)
    credentials=None
    try:
        credentials = ServicePrincipalCredentials(
             client_id=service_principal_id,
             secret=service_principal_password,
             tenant=tenant_id
          )
    except Exception as ex:
       raise CredentialsVerificationError(ex)
    
    client=None
    try:    
        client = ResourceManagementClient(credentials, subscriptionId)
    except Exception as ex:
        raise ResourceManagementError(ex)  
        
    template=None
    with open(template_file_file_path, 'r') as template_file_fd:
        template = json.load(template_file_fd)
        
    deployment_properties = {
        'properties':{
            'mode': deploy_enum,
            'template': template,
            'parameters': parameters
        }
     }
    deployment_async_operation=None
    try:
        validate=client.deployments.validate(resource_group,"azure-sample",deployment_properties)
        validate.wait()
    except Exception as ex:
        raise ActionDeploymentError(ex)    
    try:
        deployment_async_operation = client.deployments.create_or_update(
                resource_group,
                'azure-sample',
                deployment_properties
            )
        deployment_async_operation.wait()
    except Exception as ex:
        raise ActionDeploymentError(ex)
    print("Deployment done")
    print(deployment_async_operation)
    print("next----------")
    print(deployment_async_operation.kind)
    print(deployment_async_operation.properties)
    

if __name__ == "__main__":
    main()
