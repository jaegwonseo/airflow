#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

from unittest.mock import patch

import pytest
from azure.mgmt.containerinstance.models import (
    Container,
    ContainerGroup,
    Logs,
    ResourceRequests,
    ResourceRequirements,
)

from airflow.models import Connection
from airflow.providers.microsoft.azure.hooks.container_instance import AzureContainerInstanceHook


class TestAzureContainerInstanceHook:
    @pytest.fixture(autouse=True)
    def setup_test_cases(self, create_mock_connection):
        mock_connection = create_mock_connection(
            Connection(
                conn_id="azure_container_instance_test",
                conn_type="azure_container_instances",
                login="login",
                password="key",
                extra={"tenantId": "tenant_id", "subscriptionId": "subscription_id"},
            )
        )
        self.resources = ResourceRequirements(requests=ResourceRequests(memory_in_gb="4", cpu="1"))
        self.hook = AzureContainerInstanceHook(azure_conn_id=mock_connection.conn_id)
        with patch("azure.mgmt.containerinstance.ContainerInstanceManagementClient"), patch(
            "azure.common.credentials.ServicePrincipalCredentials.__init__", autospec=True, return_value=None
        ):
            yield

    @patch("azure.mgmt.containerinstance.models.ContainerGroup")
    @patch("azure.mgmt.containerinstance.operations.ContainerGroupsOperations.create_or_update")
    def test_create_or_update(self, create_or_update_mock, container_group_mock):
        self.hook.create_or_update("resource_group", "aci-test", container_group_mock)
        create_or_update_mock.assert_called_once_with("resource_group", "aci-test", container_group_mock)

    @patch("azure.mgmt.containerinstance.operations.ContainerGroupsOperations.get")
    def test_get_state(self, get_state_mock):
        self.hook.get_state("resource_group", "aci-test")
        get_state_mock.assert_called_once_with("resource_group", "aci-test", raw=False)

    @patch("azure.mgmt.containerinstance.operations.ContainerOperations.list_logs")
    def test_get_logs(self, list_logs_mock):
        expected_messages = ["log line 1\n", "log line 2\n", "log line 3\n"]
        logs = Logs(content="".join(expected_messages))
        list_logs_mock.return_value = logs

        logs = self.hook.get_logs("resource_group", "name", "name")

        assert logs == expected_messages

    @patch("azure.mgmt.containerinstance.operations.ContainerGroupsOperations.delete")
    def test_delete(self, delete_mock):
        self.hook.delete("resource_group", "aci-test")
        delete_mock.assert_called_once_with("resource_group", "aci-test")

    @patch("azure.mgmt.containerinstance.operations.ContainerGroupsOperations.list_by_resource_group")
    def test_exists_with_existing(self, list_mock):
        list_mock.return_value = [
            ContainerGroup(
                os_type="Linux",
                containers=[Container(name="test1", image="hello-world", resources=self.resources)],
            )
        ]
        assert not self.hook.exists("test", "test1")

    @patch("azure.mgmt.containerinstance.operations.ContainerGroupsOperations.list_by_resource_group")
    def test_exists_with_not_existing(self, list_mock):
        list_mock.return_value = [
            ContainerGroup(
                os_type="Linux",
                containers=[Container(name="test1", image="hello-world", resources=self.resources)],
            )
        ]
        assert not self.hook.exists("test", "not found")

    @patch("azure.mgmt.containerinstance.operations.ContainerGroupsOperations.list")
    def test_connection_success(self, mock_container_groups_list):
        mock_container_groups_list.return_value = iter([])
        status, msg = self.hook.test_connection()
        assert status is True
        assert msg == "Successfully connected to Azure Container Instance."

    @patch("azure.mgmt.containerinstance.operations.ContainerGroupsOperations.list")
    def test_connection_failure(self, mock_container_groups_list):
        mock_container_groups_list.side_effect = Exception("Authentication failed.")
        status, msg = self.hook.test_connection()
        assert status is False
        assert msg == "Authentication failed."
