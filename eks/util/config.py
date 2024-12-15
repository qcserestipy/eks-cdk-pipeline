import boto3
import copy
import json

class Config:

    @property
    def config(self):
        return self._config

    def __init__(self, config_file_path, vpc_present=True):
        with open(config_file_path, "r") as config_json:
            self._config = json.load(config_json)
        self._sessions = {}
        if not vpc_present:
            for deployment in self._config["eks"]["deployment"]:
                account_label = deployment["account"]
                account_id = self._config["accounts"][account_label]["id"]
                self._sessions[account_id] = None
            self._config = self._probe_vpc_params(self._config)
    
    def _probe_vpc_params(self, config):
        for deployment in config["eks"]["deployment"]:
            account_label = deployment["account"]
            account_id = config["accounts"][account_label]["id"]
            self._insert_nested_key(config, ["accounts", account_label], {"vpc": {}})
            if self._sessions[account_id] is None:
                self._sessions[account_id] = self._start_boto_session(account_id)
            for region in deployment["regions"]:
                ssm_client = self._sessions[account_id].client(
                    service_name="ssm",
                    region_name=region,
                )
                response = ssm_client.get_parameter(Name="/eks/vpc/vpc_id")
                vpc_id = response["Parameter"]["Value"]
                config["accounts"][account_label]["vpc"].update({region: vpc_id})
        return copy.deepcopy(config)

    def _start_boto_session(self, account_id):
        client = boto3.client("sts")
        response = client.assume_role(
            RoleArn=f"arn:aws:iam::{account_id}:role/ParameterStoreCrossAccountRole",
            RoleSessionName=f"{account_id}-ParameterStoreCrossAccountRole",
        )
        return boto3.Session(
            aws_access_key_id=response["Credentials"]["AccessKeyId"],
            aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
            aws_session_token=response["Credentials"]["SessionToken"],
        )
        
    def _insert_nested_key(self, data, keys, value):
        key = keys[0]
        if len(keys) == 1:
            data[key].update(value)
            return data
        else:
            data[key] = data.get(key, {})
            self._insert_nested_key(data[key], keys[1:], value)
