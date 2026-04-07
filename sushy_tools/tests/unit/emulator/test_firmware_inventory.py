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

from sushy_tools.emulator import main
from sushy_tools.tests.unit.emulator import test_main


@test_main.patch_resource('systems')
class FirmwareInventoryTestCase(test_main.EmulatorTestCase):

    def _setup_mocks(self, systems_mock, nics=None, systems=None):
        m = systems_mock.return_value
        m.systems = systems if systems is not None else ['test-vm']
        m.get_nics.return_value = nics if nics is not None else [
            {'id': '52:54:00:4e:5d:37', 'mac': '52:54:00:4e:5d:37'},
            {'id': '52:54:00:9a:b2:c3', 'mac': '52:54:00:9a:b2:c3'},
        ]
        return m

    def test_firmware_inventory_collection(self, systems_mock):
        self._setup_mocks(systems_mock)

        response = self.app.get('/redfish/v1/UpdateService/FirmwareInventory')

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            '#SoftwareInventoryCollection.SoftwareInventoryCollection',
            response.json['@odata.type'])
        self.assertEqual(2, response.json['Members@odata.count'])
        ids = [m['@odata.id'] for m in response.json['Members']]
        self.assertIn(
            '/redfish/v1/UpdateService/FirmwareInventory/'
            'nic-52-54-00-4e-5d-37', ids)
        self.assertIn(
            '/redfish/v1/UpdateService/FirmwareInventory/'
            'nic-52-54-00-9a-b2-c3', ids)

    def test_firmware_inventory_collection_empty(self, systems_mock):
        self._setup_mocks(systems_mock, nics=[])

        response = self.app.get('/redfish/v1/UpdateService/FirmwareInventory')

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.json['Members@odata.count'])
        self.assertEqual([], response.json['Members'])

    def test_firmware_inventory_member(self, systems_mock):
        self._setup_mocks(systems_mock)

        response = self.app.get(
            '/redfish/v1/UpdateService/FirmwareInventory/'
            'nic-52-54-00-4e-5d-37')

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            '#SoftwareInventory.v1_2_0.SoftwareInventory',
            response.json['@odata.type'])
        self.assertEqual('nic-52-54-00-4e-5d-37', response.json['Id'])
        self.assertEqual('nic:52:54:00:4e:5d:37', response.json['Name'])
        self.assertEqual('1.0.0', response.json['Version'])

    def test_firmware_inventory_member_not_found(self, systems_mock):
        self._setup_mocks(systems_mock)

        response = self.app.get(
            '/redfish/v1/UpdateService/FirmwareInventory/invalid')

        self.assertEqual(404, response.status_code)

    def test_firmware_inventory_version_configurable(self, systems_mock):
        self._setup_mocks(systems_mock, nics=[
            {'id': '52:54:00:4e:5d:37', 'mac': '52:54:00:4e:5d:37'},
        ])
        main.app.config['SUSHY_EMULATOR_NIC_FIRMWARE_VERSION'] = '2.5.0'
        self.addCleanup(
            lambda: main.app.config.pop(
                'SUSHY_EMULATOR_NIC_FIRMWARE_VERSION', None))

        response = self.app.get(
            '/redfish/v1/UpdateService/FirmwareInventory/'
            'nic-52-54-00-4e-5d-37')

        self.assertEqual(200, response.status_code)
        self.assertEqual('2.5.0', response.json['Version'])


@test_main.patch_resource('systems')
class EthernetInterfaceFirmwareVersionTestCase(test_main.EmulatorTestCase):

    system_id = 'c7a5fdbd-cdaf-9455-926a-d65c16db1809'

    def test_ethernet_interface_has_firmware_version(self, systems_mock):
        m = systems_mock.return_value
        m.uuid.return_value = self.system_id
        m.get_nics.return_value = [
            {'id': '52:54:00:4e:5d:37', 'mac': '52:54:00:4e:5d:37'},
        ]

        response = self.app.get(
            '/redfish/v1/Systems/{}/EthernetInterfaces/'
            '52:54:00:4e:5d:37'.format(self.system_id))

        self.assertEqual(200, response.status_code)
        self.assertIn('FirmwareVersion', response.json)
        self.assertEqual('1.0.0', response.json['FirmwareVersion'])

    def test_ethernet_interface_firmware_version_configurable(
            self, systems_mock):
        m = systems_mock.return_value
        m.uuid.return_value = self.system_id
        m.get_nics.return_value = [
            {'id': '52:54:00:4e:5d:37', 'mac': '52:54:00:4e:5d:37'},
        ]
        main.app.config['SUSHY_EMULATOR_NIC_FIRMWARE_VERSION'] = '3.1.0'
        self.addCleanup(
            lambda: main.app.config.pop(
                'SUSHY_EMULATOR_NIC_FIRMWARE_VERSION', None))

        response = self.app.get(
            '/redfish/v1/Systems/{}/EthernetInterfaces/'
            '52:54:00:4e:5d:37'.format(self.system_id))

        self.assertEqual(200, response.status_code)
        self.assertEqual('3.1.0', response.json['FirmwareVersion'])
