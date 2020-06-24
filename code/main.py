import os
import json
import time
import subprocess
from azureml.core import Workspace, Experiment
from azureml.core.authentication import ServicePrincipalAuthentication
from azureml.pipeline.core import PipelineRun
from azureml.exceptions import AuthenticationException, ProjectSystemException, AzureMLException, UserErrorException
from adal.adal_error import AdalError
from msrest.exceptions import AuthenticationError
from json import JSONDecodeError
from utils import AMLConfigurationException, ActionDeploymentError, AMLExperimentConfigurationException, required_parameters_provided, mask_parameter, convert_to_markdown, load_pipeline_yaml, load_runconfig_yaml, load_runconfig_python
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import DeploymentMode

def main():
    # # Loading input values
    # print("::debug::Loading input values")
    template_file = os.environ.get("INPUT_ARMTEMPLATE_FILE", default="deploy.json")
    template_params_file = os.environ.get("INPUT_ARMTEMPLATEPARAMS_FILE", default="deploy.params.json")
    azure_credentials = os.environ.get("INPUT_AZURE_CREDENTIALS", default="{}")
    resource_group = os.environ.get("INPUT_RESOURCE_GROUP", default="newresource_group")
    repo_PatToken = os.environ.get("INPUT_PATTOKEN", default="")
    self_repoName = os.environ.get("GITHUB_REPOSITORY")
    try:
        azure_credentials = json.loads(azure_credentials)
    except JSONDecodeError:
        print("::error::Please paste output of `az ad sp create-for-rbac --name <your-sp-name> --role contributor --scopes /subscriptions/<your-subscriptionId>/resourceGroups/<your-rg> --sdk-auth` as value of secret variable: AZURE_CREDENTIALS")
        raise AMLConfigurationException(f"Incorrect or poorly formed output from azure credentials saved in AZURE_CREDENTIALS secret. See setup in https://github.com/Azure/aml-workspace/blob/master/README.md")

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
    template_params_file_path = os.path.join(".cloud", ".azure", template_params_file)

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
    
    success = False
    jsonobject = None
    try:
        with open(template_params_file_path,"r") as f:
            jsonobject = json.load(f);
        jsonobject["subscriptionID"]["value"] = subscriptionId
        jsonobject["repo_name"]["value"] = self_repoName
        jsonobject["pat_token"]["value"] = repo_PatToken
        with open(template_params_file_path,"w") as f:
            json.dump(jsonobject,f)
        success = True
    except Exception as ex:
        print("error while updating parameters")
        return;
    credentials=None
    try:
        credentials = ServicePrincipalCredentials(
             client_id=service_principal_id,
             secret=service_principal_password,
             tenant=tenant_id
          )
    except Exception as ex:
       print(ex)
    client = ResourceManagementClient(credentials, subscriptionId)
    template=None
    with open(template_file_file_path, 'r') as template_file_fd:
         template = json.load(template_file_fd)
    parameters=jsonobject
    deployment_properties = {
        'properties':{
            'mode': DeploymentMode.incremental,
            'template': template,
            'parameters': parameters
        }
     }
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

if __name__ == "__main__":
    main()
