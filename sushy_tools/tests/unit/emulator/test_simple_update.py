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

from unittest import mock

from oslotest import base

from sushy_tools.emulator.controllers import update_service as us
from sushy_tools.emulator import main
from sushy_tools.tests.unit.emulator import test_main


@test_main.patch_resource('systems')
@mock.patch.dict('sushy_tools.emulator.controllers.update_service._tasks',
                 {}, clear=True)
class NicSimpleUpdateTestCase(test_main.EmulatorTestCase):

    def _setup_mocks(self, systems_mock):
        m = systems_mock.return_value
        m.systems = ['test-vm']
        m.get_nics.return_value = [
            {'id': '52:54:00:4e:5d:37', 'mac': '52:54:00:4e:5d:37'},
        ]
        return m

    @mock.patch('sushy_tools.emulator.controllers.update_service'
                '.threading.Thread')
    def test_simple_update_nic_returns_202(self, mock_thread, systems_mock):
        self._setup_mocks(systems_mock)

        response = self.app.post(
            '/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate',
            json={
                'ImageURI': 'http://server/nic-fw-2.0.0.bin',
                'Targets': [
                    '/redfish/v1/UpdateService/FirmwareInventory/'
                    'nic-52-54-00-4e-5d-37'
                ],
            })

        self.assertEqual(202, response.status_code)
        self.assertIn('/redfish/v1/TaskService/Tasks/',
                      response.headers['Location'])

    @mock.patch('sushy_tools.emulator.controllers.update_service'
                '.threading.Thread')
    def test_simple_update_network_adapter_target_returns_202(
            self, mock_thread, systems_mock):
        self._setup_mocks(systems_mock)

        response = self.app.post(
            '/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate',
            json={
                'ImageURI': 'http://server/nic-fw-2.0.0.bin',
                'Targets': [
                    '/redfish/v1/Chassis/some-chassis-id/'
                    'NetworkAdapters/00000100'
                ],
            })

        self.assertEqual(202, response.status_code)
        self.assertIn('/redfish/v1/TaskService/Tasks/',
                      response.headers['Location'])

    @mock.patch('sushy_tools.emulator.controllers.update_service'
                '.threading.Thread')
    def test_simple_update_nic_version_bumped_when_no_semver_in_uri(
            self, mock_thread, systems_mock):
        self._setup_mocks(systems_mock)
        main.app.config['SUSHY_EMULATOR_NIC_FIRMWARE_VERSION'] = '1.3.7'
        self.addCleanup(
            lambda: main.app.config.pop(
                'SUSHY_EMULATOR_NIC_FIRMWARE_VERSION', None))

        self.app.post(
            '/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate',
            json={
                'ImageURI': 'http://server/nic-firmware-latest.bin',
                'Targets': [
                    '/redfish/v1/UpdateService/FirmwareInventory/'
                    'nic-52-54-00-4e-5d-37'
                ],
            })

        version = mock_thread.call_args.kwargs['args'][3]
        self.assertEqual('1.3.8', version)

    @mock.patch('sushy_tools.emulator.controllers.update_service'
                '.threading.Thread')
    def test_simple_update_nic_system_identity_passed_to_thread(
            self, mock_thread, systems_mock):
        self._setup_mocks(systems_mock)

        self.app.post(
            '/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate',
            json={
                'ImageURI': 'http://server/nic-fw-2.0.0.bin',
                'Targets': [
                    '/redfish/v1/UpdateService/FirmwareInventory/'
                    'nic-52-54-00-4e-5d-37'
                ],
            })

        system_identity = mock_thread.call_args.kwargs['args'][4]
        self.assertEqual('test-vm', system_identity)

    @mock.patch('sushy_tools.emulator.controllers.update_service'
                '.threading.Thread')
    def test_simple_update_nic_task_initially_running(
            self, mock_thread, systems_mock):
        self._setup_mocks(systems_mock)

        response = self.app.post(
            '/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate',
            json={
                'ImageURI': 'http://server/nic-fw-2.0.0.bin',
                'Targets': [
                    '/redfish/v1/UpdateService/FirmwareInventory/'
                    'nic-52-54-00-4e-5d-37'
                ],
            })

        task_url = response.headers['Location']
        task_response = self.app.get(task_url)

        self.assertEqual(200, task_response.status_code)
        self.assertEqual('Running', task_response.json['TaskState'])
        self.assertEqual(50, task_response.json['PercentComplete'])

    def test_simple_update_missing_image_uri_returns_400(self, systems_mock):
        self._setup_mocks(systems_mock)

        response = self.app.post(
            '/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate',
            json={})

        self.assertEqual(400, response.status_code)

    @mock.patch('sushy_tools.emulator.controllers.update_service'
                '.threading.Thread')
    def test_simple_update_no_targets_treated_as_nic_update(
            self, mock_thread, systems_mock):
        self._setup_mocks(systems_mock)

        response = self.app.post(
            '/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate',
            json={'ImageURI': 'http://server/nic-fw.bin'})

        self.assertEqual(202, response.status_code)
        self.assertIn('/redfish/v1/TaskService/Tasks/',
                      response.headers['Location'])

    def test_task_not_found_returns_404(self, systems_mock):
        response = self.app.get(
            '/redfish/v1/TaskService/Tasks/nonexistent-task-uuid')

        self.assertEqual(404, response.status_code)


class NicDoUpdateTestCase(base.BaseTestCase):

    TASK_ID = 'test-task-id'

    def setUp(self):
        super().setUp()
        mock.patch(
            'sushy_tools.emulator.controllers.update_service'
            '._fetch_firmware_image',
            return_value=('fw.bin', '/tmp/fw.bin')).start()
        mock.patch(
            'sushy_tools.emulator.controllers.update_service.os.unlink'
        ).start()
        mock.patch(
            'sushy_tools.emulator.controllers.update_service.os.rmdir'
        ).start()
        self.addCleanup(mock.patch.stopall)

    def _make_task(self):
        task = {
            'Id': self.TASK_ID,
            'TaskState': 'Running',
            'TaskStatus': 'OK',
            'Messages': [],
        }
        us._tasks[self.TASK_ID] = task
        self.addCleanup(us._tasks.pop, self.TASK_ID, None)
        for key in list(main.app.config):
            if key.startswith('SUSHY_EMULATOR_NIC_FIRMWARE_VERSION'):
                self.addCleanup(main.app.config.pop, key, None)
        return task

    @mock.patch('time.sleep')
    @mock.patch.object(main.Application, 'systems',
                       new_callable=mock.PropertyMock)
    def test_do_nic_update_bumps_version_in_config(
            self, systems_mock, mock_sleep):
        self._make_task()
        us._do_nic_update(main.app, self.TASK_ID, 'http://server/fw.bin', '2.0.0', None)

        self.assertEqual(
            '2.0.0',
            main.app.config.get('SUSHY_EMULATOR_NIC_FIRMWARE_VERSION'))

    @mock.patch('time.sleep')
    @mock.patch.object(main.Application, 'systems',
                       new_callable=mock.PropertyMock)
    def test_do_nic_update_sets_task_completed(self, systems_mock, mock_sleep):
        self._make_task()
        us._do_nic_update(main.app, self.TASK_ID, 'http://server/fw.bin', '2.0.0', None)

        self.assertEqual('Completed', us._tasks[self.TASK_ID]['TaskState'])
        self.assertEqual(1, len(us._tasks[self.TASK_ID]['Messages']))

    @mock.patch('time.sleep')
    @mock.patch.object(main.Application, 'systems',
                       new_callable=mock.PropertyMock)
    def test_do_nic_update_reboots_system(self, systems_mock, mock_sleep):
        self._make_task()
        systems_mock.return_value.get_power_state.return_value = 'On'
        us._do_nic_update(main.app, self.TASK_ID, 'http://server/fw.bin', '2.0.0', 'test-vm')

        systems_mock.return_value.set_power_state.assert_called_once_with(
            'test-vm', 'GracefulRestart')

    @mock.patch('time.sleep')
    @mock.patch.object(main.Application, 'systems',
                       new_callable=mock.PropertyMock)
    def test_do_nic_update_version_applied_after_reboot(
            self, systems_mock, mock_sleep):
        self._make_task()
        systems_mock.return_value.get_power_state.return_value = 'On'

        us._do_nic_update(main.app, self.TASK_ID, 'http://server/fw.bin', '2.0.0', 'test-vm')

        self.assertEqual(
            '2.0.0',
            main.app.config.get('SUSHY_EMULATOR_NIC_FIRMWARE_VERSION'))
        self.assertEqual('Completed', us._tasks[self.TASK_ID]['TaskState'])

    @mock.patch('time.sleep')
    @mock.patch.object(main.Application, 'systems',
                       new_callable=mock.PropertyMock)
    def test_do_nic_update_version_not_applied_before_reboot_completes(
            self, systems_mock, mock_sleep):
        self._make_task()
        # VM never comes back up within poll window
        systems_mock.return_value.get_power_state.return_value = 'Off'

        us._do_nic_update(main.app, self.TASK_ID, 'http://server/fw.bin', '2.0.0', 'test-vm')

        self.assertNotEqual(
            '2.0.0',
            main.app.config.get('SUSHY_EMULATOR_NIC_FIRMWARE_VERSION'))

    @mock.patch('time.sleep')
    @mock.patch.object(main.Application, 'systems',
                       new_callable=mock.PropertyMock)
    def test_do_nic_update_reboot_failure_still_completes_task(
            self, systems_mock, mock_sleep):
        self._make_task()
        systems_mock.return_value.set_power_state.side_effect = Exception(
            'libvirt error')

        us._do_nic_update(main.app, self.TASK_ID, 'http://server/fw.bin', '2.0.0', 'test-vm')

        self.assertEqual('Completed', us._tasks[self.TASK_ID]['TaskState'])
        self.assertEqual(
            '2.0.0',
            main.app.config.get('SUSHY_EMULATOR_NIC_FIRMWARE_VERSION'))

    @mock.patch('time.sleep')
    @mock.patch.object(main.Application, 'systems',
                       new_callable=mock.PropertyMock)
    def test_do_nic_update_skips_reboot_when_no_system(
            self, systems_mock, mock_sleep):
        self._make_task()
        us._do_nic_update(main.app, self.TASK_ID, 'http://server/fw.bin', '2.0.0', None)

        systems_mock.return_value.set_power_state.assert_not_called()

    @mock.patch('time.sleep')
    @mock.patch.object(main.Application, 'systems',
                       new_callable=mock.PropertyMock)
    def test_do_nic_update_sleeps_before_acting(self, systems_mock, mock_sleep):
        self._make_task()
        us._do_nic_update(main.app, self.TASK_ID, 'http://server/fw.bin', '2.0.0', None)

        mock_sleep.assert_called_once_with(3)
