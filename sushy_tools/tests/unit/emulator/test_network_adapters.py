#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from sushy_tools import error
from sushy_tools.emulator import main
from sushy_tools.tests.unit.emulator import test_main


@test_main.patch_resource('systems')
@test_main.patch_resource('chassis')
class NetworkAdaptersTestCase(test_main.EmulatorTestCase):

    chassis_id = '48295861-2522-3561-6729-621118518810'

    def test_network_adapters_collection(self, chassis_mock, systems_mock):
        """Test GET /Chassis/{id}/NetworkAdapters returns collection"""
        chassis_mock = chassis_mock.return_value
        chassis_mock.uuid.return_value = self.chassis_id
        chassis_mock.chassis = [self.chassis_id]

        systems_mock = systems_mock.return_value
        systems_mock.systems = ['test-vm']
        systems_mock.get_network_adapters.return_value = [
            {
                'id': '00000300',
                'mac': '52:54:00:4e:5d:37',
                'pci_address': '0000:03:00.0',
                'manufacturer': 'Red Hat, Inc.',
                'model': 'Virtio 1.0',
                'part_number': 'PN-VIRTIO-03',
                'serial_number': 'SN-4E5D3700',
                'firmware_version': '1.0.0',
            }
        ]

        response = self.app.get(
            f'/redfish/v1/Chassis/{self.chassis_id}/NetworkAdapters'
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual('#NetworkAdapterCollection.NetworkAdapterCollection',
                         response.json['@odata.type'])
        self.assertEqual(1, response.json['Members@odata.count'])
        self.assertEqual(
            f'/redfish/v1/Chassis/{self.chassis_id}/NetworkAdapters/00000300',
            response.json['Members'][0]['@odata.id'])

    def test_network_adapters_collection_empty(self, chassis_mock,
                                                systems_mock):
        """Test NetworkAdapters collection with no adapters"""
        chassis_mock = chassis_mock.return_value
        chassis_mock.uuid.return_value = self.chassis_id
        chassis_mock.chassis = [self.chassis_id]

        systems_mock = systems_mock.return_value
        systems_mock.systems = ['test-vm']
        systems_mock.get_network_adapters.return_value = []

        response = self.app.get(
            f'/redfish/v1/Chassis/{self.chassis_id}/NetworkAdapters'
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.json['Members@odata.count'])
        self.assertEqual([], response.json['Members'])

    def test_network_adapter_resource(self, chassis_mock, systems_mock):
        """Test GET /Chassis/{id}/NetworkAdapters/{adapter_id}"""
        chassis_mock = chassis_mock.return_value
        chassis_mock.uuid.return_value = self.chassis_id
        chassis_mock.chassis = [self.chassis_id]

        systems_mock = systems_mock.return_value
        systems_mock.systems = ['test-vm']
        systems_mock.get_network_adapters.return_value = [
            {
                'id': '00000300',
                'mac': '52:54:00:4e:5d:37',
                'pci_address': '0000:03:00.0',
                'manufacturer': 'Red Hat, Inc.',
                'model': 'Virtio 1.0',
                'part_number': 'PN-VIRTIO-03',
                'serial_number': 'SN-4E5D3700',
                'firmware_version': '1.0.0',
            }
        ]

        response = self.app.get(
            f'/redfish/v1/Chassis/{self.chassis_id}/NetworkAdapters/00000300'
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual('#NetworkAdapter.v1_4_0.NetworkAdapter',
                         response.json['@odata.type'])
        self.assertEqual('00000300', response.json['Id'])
        self.assertEqual('Red Hat, Inc.', response.json['Manufacturer'])
        self.assertEqual('Virtio 1.0', response.json['Model'])
        self.assertEqual('PN-VIRTIO-03', response.json['PartNumber'])
        self.assertEqual('SN-4E5D3700', response.json['SerialNumber'])
        self.assertEqual(
            f'/redfish/v1/Chassis/{self.chassis_id}/NetworkAdapters/00000300',
            response.json['@odata.id'])

    def test_network_adapter_firmware_version_from_config(
            self, chassis_mock, systems_mock):
        """FirmwarePackageVersion reflects SUSHY_EMULATOR_NIC_FIRMWARE_VERSION"""
        chassis_mock = chassis_mock.return_value
        chassis_mock.uuid.return_value = self.chassis_id
        chassis_mock.chassis = [self.chassis_id]

        systems_mock = systems_mock.return_value
        systems_mock.systems = ['test-vm']
        systems_mock.get_network_adapters.return_value = [
            {
                'id': '00000300',
                'mac': '52:54:00:4e:5d:37',
                'pci_address': '0000:03:00.0',
                'manufacturer': 'Red Hat, Inc.',
                'model': 'Virtio 1.0',
                'part_number': 'PN-VIRTIO-03',
                'serial_number': 'SN-4E5D3700',
                'firmware_version': None,
            }
        ]
        main.app.config['SUSHY_EMULATOR_NIC_FIRMWARE_VERSION'] = '2.3.1'
        self.addCleanup(
            lambda: main.app.config.pop(
                'SUSHY_EMULATOR_NIC_FIRMWARE_VERSION', None))

        response = self.app.get(
            f'/redfish/v1/Chassis/{self.chassis_id}/NetworkAdapters/00000300'
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            '2.3.1',
            response.json['Controllers'][0]['FirmwarePackageVersion'])

    def test_network_adapter_not_found(self, chassis_mock, systems_mock):
        """Test GET /Chassis/{id}/NetworkAdapters/{invalid_id} returns 404"""
        chassis_mock = chassis_mock.return_value
        chassis_mock.uuid.return_value = self.chassis_id
        chassis_mock.chassis = [self.chassis_id]

        systems_mock = systems_mock.return_value
        systems_mock.systems = ['test-vm']
        systems_mock.get_network_adapters.return_value = [
            {
                'id': '00000300',
                'mac': '52:54:00:4e:5d:37',
                'pci_address': '0000:03:00.0',
                'manufacturer': 'Red Hat, Inc.',
                'model': 'Virtio 1.0',
                'part_number': 'PN-VIRTIO-03',
                'serial_number': 'SN-4E5D3700',
                'firmware_version': '1.0.0',
            }
        ]

        response = self.app.get(
            f'/redfish/v1/Chassis/{self.chassis_id}/NetworkAdapters/INVALID'
        )

        self.assertEqual(404, response.status_code)

    def test_network_adapter_feature_not_available_minimum(
            self, chassis_mock, systems_mock):
        """Test NetworkAdapters not available with minimum feature set"""
        self.set_feature_set('minimum')

        response = self.app.get(
            f'/redfish/v1/Chassis/{self.chassis_id}/NetworkAdapters'
        )

        self.assertIn(response.status_code, [404, 500])


@test_main.patch_resource('indicators')
@test_main.patch_resource('managers')
@test_main.patch_resource('systems')
@test_main.patch_resource('chassis')
class NetworkAdaptersConditionalExposureTestCase(test_main.EmulatorTestCase):
    """Test conditional exposure of NetworkAdapters in Chassis resource"""

    def test_network_adapters_advertised_when_supported(
            self, chassis_mock, systems_mock, managers_mock, indicators_mock):
        """Test NetworkAdapters link shown in Chassis when driver supports"""
        chassis_mock = chassis_mock.return_value
        chassis_mock.chassis = ['xxxx-yyyy-zzzz']
        chassis_mock.uuid.return_value = 'xxxx-yyyy-zzzz'
        chassis_mock.name.return_value = 'Chassis'

        systems_mock = systems_mock.return_value
        systems_mock.systems = ['sys1']
        systems_mock.get_network_adapters.return_value = [{'id': '00000300'}]

        managers_mock.return_value.managers = ['man1']
        indicators_mock.return_value.get_indicator_state.return_value = 'Off'

        response = self.app.get('/redfish/v1/Chassis/xxxx-yyyy-zzzz')

        self.assertEqual(200, response.status_code)
        self.assertIn('NetworkAdapters', response.json)
        self.assertEqual(
            '/redfish/v1/Chassis/xxxx-yyyy-zzzz/NetworkAdapters',
            response.json['NetworkAdapters']['@odata.id'])

    def test_network_adapters_not_advertised_when_not_supported(
            self, chassis_mock, systems_mock, managers_mock, indicators_mock):
        """Test NetworkAdapters link hidden when driver doesn't support"""
        chassis_mock = chassis_mock.return_value
        chassis_mock.chassis = ['xxxx-yyyy-zzzz']
        chassis_mock.uuid.return_value = 'xxxx-yyyy-zzzz'
        chassis_mock.name.return_value = 'Chassis'

        systems_mock = systems_mock.return_value
        systems_mock.systems = ['sys1']
        systems_mock.get_network_adapters.side_effect = (
            error.NotSupportedError)

        managers_mock.return_value.managers = ['man1']
        indicators_mock.return_value.get_indicator_state.return_value = 'Off'

        response = self.app.get('/redfish/v1/Chassis/xxxx-yyyy-zzzz')

        self.assertEqual(200, response.status_code)
        self.assertNotIn('NetworkAdapters', response.json)
