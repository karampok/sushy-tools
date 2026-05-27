# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

sushy-tools provides Redfish protocol simulators for development and testing of the Sushy library. It ships two
simulators:
- sushy-static: A static read-only REST API responder
- sushy-emulator: A virtual Redfish BMC backed by libvirt, OpenStack Nova, or Ironic

This is an OpenStack project following OpenStack development practices.

## Development Workflow

Changes are submitted via Gerrit (not GitHub PRs). Run `git review` to submit patches.

### Commit Messages

Include "Assisted-By: Claude Code/claude-sonnet-4.5" when AI assistance was used. Follow standard OpenStack commit
message format with Change-Id footer.

### Release Notes

Add release notes for user-visible changes using reno. Create YAML files in releasenotes/notes/:

```bash
# Release note sections: features, fixes, issues, upgrade, deprecations, critical
reno new my-feature-name
# Edit the generated YAML file in releasenotes/notes/
```

Format example:
```yaml
---
features:
  - |
    Adds support for feature X which enables Y.
fixes:
  - |
    Fixes issue where Z occurred during W.
```

## Common Commands

### Testing

```bash
# Run all unit tests
tox -e py3

# Run specific test file
stestr run sushy_tools.tests.unit.emulator.test_main

# Run single test case
tox -e debug -- sushy_tools.tests.unit.emulator.test_main.TestCase.test_method

# Run with test pattern
stestr run --no-discover sushy_tools.tests.unit.emulator.test_main.CommonTestCase

# Run linting checks (hacking, flake8, codespell, etc.)
tox -e pep8

# Run codespell only
tox -e codespell

# Run tests with coverage
tox -e cover
```

CI runs stestr for unit tests plus Ironic Tempest integration tests in two configurations:
- sushy-tools-tempest-bios-redfish-pxe: BIOS boot mode with PXE
- sushy-tools-tempest-uefi-redfish-vmedia: UEFI boot mode with virtual media

Check and gate pipelines both run these integration tests. Codespell runs in check but is non-voting.

### Building Documentation

```bash
# HTML documentation
tox -e docs

# Release notes
tox -e releasenotes
```

### Running the Emulators

```bash
# Static emulator
sushy-static

# Emulator with libvirt backend
sushy-emulator --libvirt-uri "qemu:///system"

# Emulator with OpenStack Nova backend
sushy-emulator --os-cloud mycloud

# Using config file
SUSHY_EMULATOR_CONFIG=/path/to/config.conf sushy-emulator
```

Configuration can be via command-line flags or environment variable SUSHY_EMULATOR_CONFIG pointing to a Flask config
file with SUSHY_EMULATOR_* prefixed options.

## Architecture

### Driver-Based Design

The emulator uses a driver pattern for virtualization backends. All drivers inherit from AbstractSystemsDriver
(sushy_tools/emulator/resources/systems/base.py):

- FakeDriver: Static fake systems for testing
- LibvirtDriver: Controls libvirt VMs (default if --libvirt-uri specified)
- OpenStackDriver (novadriver.py): Controls OpenStack Nova instances (if SUSHY_EMULATOR_OS_CLOUD set)
- IronicDriver: Controls Ironic bare metal nodes (if SUSHY_EMULATOR_IRONIC_CLOUD set)

The driver is selected automatically based on configuration. Only one driver is active per emulator instance.

### Driver Feature Support Matrix

Not all drivers support all Redfish features. Current support matrix:

| Feature        | libvirt | nova | ironic | fake |
|----------------|---------|------|--------|------|
| Power control  | ✓       | ✓    | ✓      | ✓    |
| Boot device    | ✓       | ✓    | ✓      | ✓    |
| Boot mode      | ✓       | ✓    | ✓      | ✓    |
| BIOS           | ✓       | ✗    | ✗      | ✗    |
| Processors     | ✓       | ✗    | ✗      | ✗    |
| SimpleStorage  | ✓       | ✗    | ✗      | ✗    |
| Virtual Media  | ✓       | ✓    | ✓      | ✗    |
| Secure Boot    | ✓       | ✗    | ✓      | ✗    |

LibvirtDriver is the most feature-complete. When adding new features, consider which drivers can support them. The
emulator conditionally exposes sub-resources based on driver capabilities.

### Driver Interface

AbstractSystemsDriver defines the contract for all backends:
- systems: List available systems (VMs/instances)
- get_power_state/set_power_state: Power management
- get_boot_device/set_boot_device: Boot order control
- get_boot_mode/set_boot_mode: UEFI vs Legacy
- get_total_memory/get_total_cpus: Hardware properties
- Optional methods for advanced features (processors, secure boot, virtual media)

When adding functionality, check if the driver supports it via the abstract methods. Not all drivers support all
features.

When adding new methods to AbstractSystemsDriver, ensure they raise NotImplementedError by default or provide sensible
base implementation. All four concrete drivers must implement or inherit new abstract methods. Test that drivers
without support properly handle unsupported features.

### Driver-Specific Implementation Notes

LibvirtDriver:
- Uses SSH connections which can create zombie processes. SIGCHLD handler in main.py cleans these up automatically.
- Supports most advanced features including BIOS configuration and processor enumeration.
- Boot device handling can be configured to ignore boot device settings (SUSHY_EMULATOR_IGNORE_BOOT_DEVICE) to rely on
  UEFI Boot Manager.

OpenStackDriver (Nova):
- Should fetch real-time instance data from Nova API, not use cached state, to avoid stale power_state and task_state.
- Helper methods should poll with exponential backoff when instance has active task_state, returning 503 to signal
  clients to retry.
- Handle instance rebuilds and power state transitions carefully to avoid ConflictException errors.

### Flask Application Structure

Main Flask app in sushy_tools/emulator/main.py defines Redfish REST endpoints:
- /redfish/v1/Systems: Computer systems (VMs/instances)
- /redfish/v1/Chassis: Physical/logical chassis
- /redfish/v1/Managers: BMC managers

Controllers (sushy_tools/emulator/controllers/) handle specific features like virtual media and update service.
Resources (sushy_tools/emulator/resources/) map Redfish resources to driver backends.

Templates (sushy_tools/emulator/templates/) contain Jinja2 JSON templates for Redfish responses.

### Feature Sets

The emulator supports three feature sets (SUSHY_EMULATOR_FEATURE_SET):
- minimum: Only Systems endpoints
- vmedia: Systems + Managers + VirtualMedia
- full: All endpoints including Chassis

## Testing Conventions

Tests use unittest and oslotest.BaseTestCase. Mock virtualization backends using mock.patch.

Test files follow test_<module>.py naming in sushy_tools/tests/unit/ mirroring the source structure.

Common test patterns:
- EmulatorTestCase: Base class that sets up app.test_client()
- patch_resource decorator: Mocks Application properties (systems, managers, etc.)
- XML fixtures in tests/unit/emulator/: Libvirt domain XML for testing libvirtdriver

## Code Style

Follow OpenStack hacking guidelines enforced by pre-commit hooks:
- flake8 with hacking extensions
- import-order-style: pep8
- codespell for spell checking
- trailing whitespace, line ending fixes
- YAML/JSON validation

Run checks before submitting:
```bash
# Run all pre-commit hooks via tox
tox -e pep8

# Install pre-commit hooks locally (optional)
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

## Python Version

Requires Python 3.10+. Test with `tox -e py3` which uses python3 from PATH.
