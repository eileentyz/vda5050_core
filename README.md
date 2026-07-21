# VDA5050 Library and Support Tools

`vda5050_core` is a modern C++ library for developing applications that communicate using the VDA5050 specification. It provides reusable components for both AGV-side and master-control implementations, including message types along with serialization and deserialization utilities, validation, execution utilities, MQTT communication and a high-level adapter API for robot integration.

The library is runtime framework-independent and can be integrated into standalone C++ applications, ROS 2 systems or existing robot software. It uses `ament_cmake` as its build system.

```
VDA5050 Master
      │ MQTT
      ▼
vda5050_core AGV Client
      │ navigation, action and state callbacks
      ▼
Robot SDK / REST API / ROS 2 Integration
      │
      ▼
    Robot
```

> **Status:** This project is under active development.

## Features

- **VDA5050 message types** represented as plain C++ structs.
- **JSON serialization and deserialization** for native types and optional ROS 2 `vda5050_interfaces` messages.
- **Validation** of orders, instant actions, protocol limits, action conflicts, factsheet alignment and graph traversability.
- **MQTT transport** built on Eclipse Paho.
- **An execution framework** for composing reactive, non-blocking robot logic.
- **A high-level AGV client adapter** for navigation, actions and state reporting.
- **Layout Interchange Format support** for loading and validating facility graphs.
- **Python bindings**, including helpers for migrating Open-RMF fleet adapters.

## Documentation


| Document                                                    | Contents                                    |
| ----------------------------------------------------------- | ------------------------------------------- |
| [Client Adapter Guide](vda5050_core/docs/client-adapter.md) | Integrating an AGV using the client adapter |
| [RMF Migration Guide](vda5050_core/docs/rmf-migration.md)   | Migrating an Open-RMF fleet adapter         |
| [Design Guide](vda5050_core/docs/design.md)                 | Architecture and design rationale           |
| [Execution Guide](vda5050_core/docs/execution.md)           | Building custom execution logic             |
| [Types Guide](vda5050_core/docs/types.md)                   | Message types and JSON conversion           |


To connect an existing robot SDK, REST API or ROS 2 navigation system, start with the [Client Adapter Guide](vda5050_core/docs/client-adapter.md).

To understand or extend the library architecture, start with the [Design Guide](vda5050_core/docs/design.md).

## Requirements

- C++17
- CMake 3.8 or newer
- [Eclipse Paho MQTT C++](https://github.com/eclipse-paho/paho.mqtt.cpp)
- [nlohmann/json](https://github.com/nlohmann/json)
- [fmt](https://github.com/fmtlib/fmt)
- `pybind11` when building the Python bindings
- `vda5050_interfaces` when `ENABLE_ROS2=ON`

The package uses `ament_cmake` and is tested with ROS 2 Humble and Jazzy, GCC and Clang.

## Building

Install the package dependencies in a sourced ROS 2 environment:

```bash
sudo apt update
sudo apt install python3-rosdep ros-${ROS_DISTRO}-ament-cmake-python
```

Create a workspace and build the package:

```bash
mkdir -p ~/vda5050_ws/src
cd ~/vda5050_ws/src

git clone https://github.com/ros-industrial/vda5050_core.git

cd ~/vda5050_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --packages-select vda5050_core
source install/setup.bash
```

### Build Options

| Option           | Default | Effect                                                  |
| ---------------- | ------- | ------------------------------------------------------- |
| `ENABLE_ROS2`    | `OFF`   | Enables support for ROS 2 `vda5050_interfaces` messages |
| `BUILD_PYTHON`   | `ON`    | Builds the Python bindings                              |
| `BUILD_EXAMPLES` | `ON`    | Builds the examples                                     |
| `BUILD_TESTING`  | `ON`    | Builds the tests and configured linters                 |


For example, enable ROS 2 message support with:

```bash
colcon build \
  --packages-select vda5050_core \
  --cmake-args -DENABLE_ROS2=ON
```

## Quick Start

The following example shows the basic setup for an AGV-side client.

It creates the MQTT transport and VDA5050 client adapter, then registers a navigation callback. In a real application, the callback should forward the request to the robot's navigation system.

```cpp
#include <iostream>

#include "vda5050_core/client/adapter/adapter.hpp"
#include "vda5050_core/execution/protocol_adapter.hpp"
#include "vda5050_core/transport/mqtt_client_interface.hpp"

using namespace vda5050_core;

int main()
{
  auto mqtt_client = transport::create_default_client_unique(
    "tcp://localhost:1883",
    "agv_1");

  auto protocol_adapter = execution::ProtocolAdapter::make(
    std::move(mqtt_client),
    "uagv",
    "2.0.0",
    "Manufacturer",
    "S001");

  auto adapter = client::adapter::Adapter::make(protocol_adapter);

  adapter->on_navigate(
    [](auto node_request, auto edge_request, auto execution)
    {
      // Forward the request to the robot navigation system.
      //
      // This demonstration reports completion immediately.
      // A real integration should only report completion after
      // the robot reaches the requested node.
      execution->finished();
    });

  adapter->start();

  // Keep processing orders until Enter is pressed.
  std::cin.get();

  adapter->stop();
  return 0;
}
```

CMake integration:

```cmake
find_package(vda5050_core REQUIRED)

target_link_libraries(
  my_agv
  PRIVATE
  vda5050_core::client
)
```

For a complete integration covering navigation, actions, localization, cancellation and state reporting, see the [Client Adapter Guide](vda5050_core/docs/client-adapter.md) and [`vda5050_core/examples/client/adapter_example.cpp`](vda5050_core/examples/client/adapter_example.cpp).

## Examples

The following examples can be run against a local MQTT broker:

```bash
mosquitto -v
```

| Example                                                   | Demonstrates                              |
| --------------------------------------------------------- | ----------------------------------------- |
| `vda5050_core/examples/client/adapter_example.cpp`        | AGV client-adapter integration            |
| `vda5050_core/examples/master/order_publisher.cpp`        | Dispatching a VDA5050 order               |
| `vda5050_core/examples/execution/handler_integration.cpp` | Context, strategy and handler integration |
| `vda5050_core/examples/execution/engine_example.cpp`      | Event queues and wait conditions          |
| `vda5050_core/examples/execution/provider_example.cpp`    | Update broadcasting                       |
| `vda5050_core/examples/execution/custom_base.cpp`         | Defining custom updates and events        |


## Repository Structure

```
vda5050_core/
  include/vda5050_core/
    types/        VDA5050 message structs
    json_utils/   JSON serialization and traits
    validation/   Specification compliance checks
    errors/       Error codes and factories
    transport/    MQTT client interface and implementation
    execution/    Reactive execution framework
    client/       AGV-side client and adapter
    master/       Master-control components
    layout/       Layout Interchange Format support
    logger/       Logging
  examples/       Runnable examples
  python/         Python bindings
  test/           Unit and integration tests
  docs/           Documentation
```

## Testing

Run the test suite with:

```bash
colcon test --packages-select vda5050_core
colcon test-result --verbose
```

Some integration tests require an MQTT broker running on `localhost:1883`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and contribution guidelines.

Commits must include a `Signed-off-by` line certifying the [Developer Certificate of Origin](https://developercertificate.org/).

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.