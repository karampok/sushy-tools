  Add dummy NIC firmware support to the sushy-tools libvirt emulator.

  Context:
  - GET /redfish/v1/UpdateService/FirmwareInventory currently returns 404
  - GET /redfish/v1/Systems/{id}/EthernetInterfaces/{mac} returns NIC info but no FirmwareVersion field
  - Ironic's redfish firmware interface reads FirmwareInventory to discover NIC firmware components, which metal3 baremetal-operator maps to HostFirmwareComponents with a nic: prefix

  Requirements:
  1. Implement GET /redfish/v1/UpdateService and GET /redfish/v1/UpdateService/FirmwareInventory endpoints
  2. The inventory should include one entry per NIC discovered from the system's EthernetInterfaces, using the NIC's MAC address as identifier
  3. Each NIC entry should expose a configurable dummy Version (default: 1.0.0) and Name following the pattern nic:{mac}
  4. The firmware version should be configurable via the existing sushy config file mechanism (e.g. SUSHY_EMULATOR_NIC_FIRMWARE_VERSION)
  5. GET /redfish/v1/Systems/{id}/EthernetInterfaces/{mac} should include FirmwareVersion matching the inventory entry

  Goal: Allow Ironic inspection to discover and report NIC firmware versions so metal3 HostFirmwareComponents is populated with nic: entries.
