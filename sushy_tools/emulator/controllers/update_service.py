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

import os
import re
import tempfile
import threading
import time
import uuid
from urllib import parse as urlparse

import flask
import requests

from sushy_tools import error
from sushy_tools.emulator import api_utils

_tasks = {}

KNOWN_NIC_MODELS = ['virtio', 'e1000e', 'e1000', 'igb', 'rtl8139']


def _firmware_filename_from_response(image_url, rsp, tmp_file):
    """Write response body to tmp_file; return resolved filename.

    Mirrors vmedia._write_from_response: prefers Content-Disposition header,
    falls back to URL basename.
    """
    with open(tmp_file.name, 'wb') as fl:
        for chunk in rsp.iter_content(chunk_size=8192):
            if chunk:
                fl.write(chunk)

    local_file = None

    content_dsp = rsp.headers.get('content-disposition')
    if content_dsp:
        local_file = re.findall('filename="(.+)"', content_dsp)

    if local_file:
        local_file = local_file[0]

    if not local_file:
        parsed_url = urlparse.urlparse(image_url)
        local_file = os.path.basename(parsed_url.path)

    if not local_file:
        local_file = 'firmware.bin'

    return local_file


def _fetch_firmware_image(image_url):
    """Download firmware image; return (filename, local_file_path).

    Mirrors vmedia._get_image without auth/cert options.
    Caller is responsible for cleaning up local_file_path.
    """
    try:
        with requests.get(image_url, stream=True, timeout=5) as rsp:
            if rsp.status_code >= 400:
                api_utils.warning(
                    'Failed fetching firmware from URL %s: HTTP %s',
                    image_url, rsp.status_code)
                raise error.FishyError(
                    'Cannot download firmware: got error %s from the server'
                    % rsp.status_code)

            with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tmp:
                filename = _firmware_filename_from_response(
                    image_url, rsp, tmp)
                temp_dir = tempfile.mkdtemp(dir=os.path.dirname(tmp.name))
                local_file_path = os.path.join(temp_dir, filename)

            os.rename(tmp.name, local_file_path)
    except error.FishyError:
        raise
    except Exception as exc:
        raise error.FishyError(
            'Failed fetching firmware from URL %s: %s' % (image_url, exc))

    return filename, local_file_path


def _model_from_filename(filename):
    """Extract NIC model type from a firmware image filename, or None."""
    name = filename.lower()
    for model in KNOWN_NIC_MODELS:
        if model in name:
            return model
    return None


def _model_from_uri(uri):
    """Extract NIC model type from firmware image URI filename, or None."""
    name = uri.rstrip('/').rsplit('/', 1)[-1].lower()
    for model in KNOWN_NIC_MODELS:
        if model in name:
            return model
    return None


def _nic_firmware_key(model_type=None):
    if model_type:
        return 'SUSHY_EMULATOR_NIC_FIRMWARE_VERSION_' + model_type.upper()
    return 'SUSHY_EMULATOR_NIC_FIRMWARE_VERSION'


def _get_nic_version(app_or_current_app, model_type=None):
    """Return firmware version for a given NIC model, falling back to default."""
    if model_type:
        key = _nic_firmware_key(model_type)
        val = app_or_current_app.config.get(key)
        if val:
            return val
    return app_or_current_app.config.get(
        'SUSHY_EMULATOR_NIC_FIRMWARE_VERSION', '1.0.0')


def _do_nic_update(app, task_id, image_uri, version, system_identity,
                   model_type=None):
    time.sleep(3)

    with app.app_context():
        # Fetch firmware image to resolve real filename (Content-Disposition
        # preferred over URL basename), then refine model_type if not already
        # known.
        local_file_path = None
        try:
            filename, local_file_path = _fetch_firmware_image(image_uri)
            detected = _model_from_filename(filename)
            if detected is not None:
                model_type = detected
        except Exception as exc:
            api_utils.warning(
                'Failed to fetch firmware image "%s": %s — '
                'using URI-based model detection', image_uri, exc)

        if local_file_path:
            try:
                os.unlink(local_file_path)
                os.rmdir(os.path.dirname(local_file_path))
            except Exception:
                pass

        rebooted = False
        if system_identity:
            try:
                app.systems.set_power_state(system_identity, 'GracefulRestart')
                rebooted = True
            except Exception as exc:
                api_utils.warning(
                    'Failed to reboot system "%s" after NIC firmware update: %s',
                    system_identity, exc)

        config_key = _nic_firmware_key(model_type)
        if rebooted:
            for _ in range(12):
                time.sleep(5)
                try:
                    if app.systems.get_power_state(system_identity) == 'On':
                        app.config[config_key] = version
                        break
                except Exception:
                    pass
        else:
            app.config[config_key] = version

        _tasks[task_id]['TaskState'] = 'Completed'
        _tasks[task_id]['Messages'].append(
            {'Message': 'NIC firmware updated to %s' % version})


update_service = flask.Blueprint(
    'UpdateService', __name__,
    url_prefix='/redfish/v1/UpdateService/')


@update_service.route('', methods=['GET'])
@api_utils.returns_json
def update_service_resource():
    api_utils.debug('Serving update service resources')

    return flask.render_template(
        'update_service.json'
    )


@update_service.route('/FirmwareInventory', methods=['GET'])
@api_utils.returns_json
def firmware_inventory_collection():
    api_utils.debug('Serving firmware inventory collection')

    members = []
    seen_macs = set()
    for system in flask.current_app.systems.systems:
        # Build MAC -> model_type map from network adapters
        mac_model = {}
        try:
            for adapter in flask.current_app.systems.get_network_adapters(
                    system):
                mac_model[adapter['mac']] = adapter.get('model_type')
        except Exception:
            pass

        try:
            nics = flask.current_app.systems.get_nics(system)
        except Exception as exc:
            api_utils.warning(
                'Failed to get NICs for system "%s": %s', system, exc)
            continue
        for nic in nics:
            mac = nic['id']
            if mac in seen_macs:
                continue
            seen_macs.add(mac)
            model_type = mac_model.get(mac)
            members.append({
                'id': 'nic-' + mac.replace(':', '-'),
                'name': 'nic:' + mac,
                'version': _get_nic_version(flask.current_app, model_type),
            })

    return flask.render_template(
        'firmware_inventory.json',
        members=members)


@update_service.route('/FirmwareInventory/<member_id>', methods=['GET'])
@api_utils.returns_json
def firmware_inventory_member(member_id):
    api_utils.debug('Serving firmware inventory member "%s"', member_id)

    for system in flask.current_app.systems.systems:
        # Build MAC -> model_type map from network adapters
        mac_model = {}
        try:
            for adapter in flask.current_app.systems.get_network_adapters(
                    system):
                mac_model[adapter['mac']] = adapter.get('model_type')
        except Exception:
            pass

        try:
            nics = flask.current_app.systems.get_nics(system)
        except Exception as exc:
            api_utils.warning(
                'Failed to get NICs for system "%s": %s', system, exc)
            continue
        for nic in nics:
            mac = nic['id']
            if 'nic-' + mac.replace(':', '-') == member_id:
                model_type = mac_model.get(mac)
                member = {
                    'id': member_id,
                    'name': 'nic:' + mac,
                    'version': _get_nic_version(
                        flask.current_app, model_type),
                }
                return flask.render_template(
                    'firmware_inventory_member.json',
                    member=member)

    # Fallback: VM may be temporarily unavailable (e.g. mid-reboot after
    # firmware update). If the member_id matches the nic-XX-XX-XX-XX-XX-XX
    # pattern, return the config version rather than 404.
    m = re.fullmatch(
        r'nic-([0-9a-f]{2}(?:-[0-9a-f]{2}){5})', member_id, re.IGNORECASE)
    if m:
        mac = m.group(1).replace('-', ':')
        api_utils.warning(
            'NIC "%s" not found via live enumeration, returning config '
            'version (system may be rebooting)', member_id)
        member = {
            'id': member_id,
            'name': 'nic:' + mac,
            'version': _get_nic_version(flask.current_app),
        }
        return flask.render_template('firmware_inventory_member.json',
                                     member=member)

    raise error.NotFound()


@update_service.route('/Actions/UpdateService.SimpleUpdate',
                      methods=['POST'])
@api_utils.returns_json
def update_service_simple_update():
    api_utils.debug('SimpleUpdate request body: %s', flask.request.json)
    image_uri = flask.request.json.get('ImageURI')
    targets = flask.request.json.get('Targets') or []
    if not image_uri:
        message = "Missing ImageURI."
        return flask.render_template('error.json', message=message), 400

    nic_targets = [t for t in targets
                   if 'FirmwareInventory/nic-' in t
                   or '/NetworkAdapters/' in t]
    # Targets is optional per Redfish spec; no targets means update all NICs
    if nic_targets or not targets:
        for t in targets:
            if t not in nic_targets:
                api_utils.warning('SimpleUpdate target "%s" is not a NIC '
                                  'target, ignoring', t)
        # Use URI basename for initial model detection; the background thread
        # will refine this by fetching the image and reading Content-Disposition.
        model_type = _model_from_uri(image_uri)
        current = _get_nic_version(flask.current_app, model_type)
        parts = current.split('.')
        parts[-1] = str(int(parts[-1]) + 1)
        version = '.'.join(parts)

        task_id = str(uuid.uuid4())
        _tasks[task_id] = {
            'Id': task_id,
            'TaskState': 'Running',
            'TaskStatus': 'OK',
            'Messages': [],
        }

        system_identity = None
        try:
            systems = flask.current_app.systems.systems
            if systems:
                system_identity = systems[0]
        except Exception:
            pass

        app = flask.current_app._get_current_object()
        threading.Thread(
            target=_do_nic_update,
            args=(app, task_id, image_uri, version, system_identity,
                  model_type),
            daemon=True,
        ).start()

        response = flask.make_response('', 202)
        response.headers['Location'] = (
            '/redfish/v1/TaskService/Tasks/' + task_id)
        return response

    for target in targets:
        # NOTE(janders) since we only support BIOS let's ignore Manager targets
        if "Manager" in target:
            message = "Manager is not currently a supported Target."
            return flask.render_template('error.json', message=message), 400
        try:
            name = target.rstrip("/").rsplit('/', 1)[-1]
            system_uuid = flask.current_app.systems.uuid(name)
        except error.AliasAccessError as exc:
            api_utils.debug('Received a redirect in response to GET System '
                            '"%s". New System ID: "%s"', name, exc)
            system_uuid = str(exc)
        except Exception as exc:
            api_utils.debug('Encountered exception "%s" while attempting to '
                            'GET System "%s"', exc, name)
            raise

        # NOTE(janders) iterate over the array? narrow down which one is needed
        # first? I suppose the former since we may want to update multiple
        api_utils.debug('Fetching BIOS information for System "%s"',
                        system_uuid)
        try:
            versions = flask.current_app.systems.get_versions(system_uuid)

        except error.NotSupportedError as ex:
            api_utils.warning(
                'System failed to fetch BIOS information with exception %s',
                ex)
            message = "Failed fetching BIOS information"
            return flask.render_template('error.json', message=message), 500

        bios_version = versions.get('BiosVersion')

        api_utils.debug('Current BIOS version for System "%s" is "%s" ,'
                        'attempting upgrade.',
                        system_uuid, bios_version)

        bios_version = bios_version.split('.')
        bios_version[1] = str(int(bios_version[1]) + 1)
        bios_version = '.'.join(bios_version)
        firmware_versions = {"BiosVersion": bios_version}

        try:
            flask.current_app.systems.set_pending_versions(
                system_uuid, firmware_versions)
        except error.NotSupportedError as ex:
            api_utils.warning('System failed to update bios with exception %s',
                              ex)
            message = "Failed updating BIOS version"
            return flask.render_template('error.json', message=message), 500

        api_utils.info(
            'Emulated BIOS upgrade staged for System %s, '
            'new version "%s" will be applied on next reboot.',
            system_uuid, bios_version)
    return '', 204, {'Location': '/redfish/v1/TaskService/Tasks/42'}
