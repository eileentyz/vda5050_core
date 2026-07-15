# VDA5050 Library and Support Tools

`vda5050_core` is a modern C++ library for developing applications that communicate using VDA5050 specification. It provides reusable components for both AGV-side and master-control implementations, including message types along with serialization and deserialization utilities, validation, execution utilities, MQTT communication and a high-level adapter API for robot integration.

The library is framework independent and can be integrated into standalone C++ applications, ROS 2 systems or existing robot software.

> **Project status:** This project is under 🚧 active development. APIs and behavior may change as VDA5050 support evolves.

## Features

- **Complete VDA5050 message types** as plain C++ structs, with no dependency beyond the standard library.
- **JSON serialization** that also works with ROS 2 vda5050_interfaces messages from the same implementation.
- **Validation** of orders, instant actions, protocol limits, action conflicts, factsheet alignment and graph traversability.
- **MQTT transport** built on Eclipse Paho, behind an interface that can be replaced or shared with other services.
- **An execution framework** for composing reactive, non-blocking robot logic.
- **A high-level AGV client** that turns VDA5050 orders into navigation and action callbacks.
- **Layout (LIF) support** for loading and validating facility graphs.
- **Python bindings**, including a compatibility layer for migrating Open-RMF fleet adapters.

## Layout

```
vda5050_core/
  include/vda5050_core/
    types/        VDA5050 message structs
    json_utils/   JSON serialization and traits
    validation/   Specification compliance checks
    errors/       Error codes and factories
    transport/    MQTT client interface and Paho implementation
    execution/    Reactive execution framework
    client/       AGV-side client and adapter
    master/       Master-control side components
    layout/       Layout Interchange Format (LIF)
    logger/       Logging
  examples/       Runnable examples
  python/         Python bindings
  test/           Unit and integration tests
  docs/           Documentation
```



## Documentation


| Document                                                      | Contents                                         |
| ------------------------------------------------------------- | ------------------------------------------------ |
| `[docs/design.md](vda5050_core/docs/design.md)`               | Architecture and design rationale                |
| `[docs/execution.md](vda5050_core/docs/execution.md)`         | Building custom logic on the execution framework |
| `[docs/client-adapter.md](vda5050_core/docs/client-adapter.md)`             | Integrating an AGV using the client adapter      |
| `[docs/types.md](vda5050_core/docs/types.md)` | Message types and JSON conversion                |
| `[docs/rmf-migration.md](vda5050_core/docs/rmf-migration.md)` | Porting an Open-RMF fleet adapter                |


Start with `adapter.md` to integrate a robot; start with `design.md` to understand or extend the library.

## Requirements

- C++17
- CMake 3.8 or newer
- [Eclipse Paho MQTT C++](https://github.com/eclipse-paho/paho.mqtt.cpp) 1.5.0
- [nlohmann/json](https://github.com/nlohmann/json)
- [fmt](https://github.com/fmtlib/fmt)
- pybind11 (only for the Python bindings)
- `vda5050_interfaces` (only when `ENABLE_ROS2=ON`)

The package builds with `ament_cmake` and is tested against ROS 2 Humble and Jazzy, with GCC and Clang, under address and thread sanitizers.

## Building

```bash
sudo apt install libpaho-mqtt-dev libpaho-mqttpp-dev

mkdir -p ws/src && cd ws/src
git clone https://github.com/ros-industrial/vda5050_core.git
cd ..

colcon build --packages-select vda5050_core
source install/setup.bash
```



### Options


| Option           | Default | Effect                                                          |
| ---------------- | ------- | --------------------------------------------------------------- |
| `ENABLE_ROS2`    | `OFF`   | Serialize `vda5050_interfaces` messages as well as native types |
| `BUILD_PYTHON`   | `ON`    | Build the Python bindings                                       |
| `BUILD_EXAMPLES` | `ON`    | Build the examples                                              |
| `BUILD_TESTING`  | `ON`    | Build the tests and run linters                                 |


```bash
colcon build --cmake-args -DENABLE_ROS2=ON
```



## Quick Start

An AGV client that answers orders from a master control:

```cpp
#include "vda5050_core/client/adapter/adapter.hpp"
#include "vda5050_core/execution/protocol_adapter.hpp"
#include "vda5050_core/transport/mqtt_client_interface.hpp"

using namespace vda5050_core;

int main()
{
  auto mqtt_client = transport::create_default_client_unique(
    "tcp://localhost:1883", "agv_1");

  auto protocol_adapter = execution::ProtocolAdapter::make(
    std::move(mqtt_client), "uagv", "2.0.0", "Manufacturer", "S001");

  auto adapter = client::adapter::Adapter::make(protocol_adapter);

  adapter->on_navigate(
    [](auto node_request, auto edge_request, auto execution) {
      // Drive to node_request.node_position(), then:
      execution->finished();
    });

  adapter->start();

  // ... run ...

  adapter->stop();
}
```

CMake integration:

```cmake
find_package(vda5050_core REQUIRED)

target_link_libraries(my_agv PRIVATE vda5050_core::client)
```

Available targets: `vda5050_core::types`, `::json_utils`, `::validation`, `::errors`, `::transport`, `::execution`, `::client`, `::master`, `::layout`, `::logger`.

## Examples

Runnable against a local broker (`mosquitto -d`):


| Example                                      | Shows                                  |
| -------------------------------------------- | -------------------------------------- |
| `examples/client/adapter_example.cpp`        | A complete AGV client                  |
| `examples/master/order_publisher.cpp`        | Dispatching an order                   |
| `examples/execution/handler_integration.cpp` | Context, Strategy and Handler together |
| `examples/execution/engine_example.cpp`      | Event queues and wait conditions       |
| `examples/execution/provider_example.cpp`    | Update broadcast                       |
| `examples/execution/custom_base.cpp`         | Defining custom Updates and Events     |




## Testing

```bash
colcon test --packages-select vda5050_core
colcon test-result --verbose
```

Integration tests need a broker on `localhost:1883`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Commits must carry a `Signed-off-by` line certifying the [Developer Certificate of Origin](https://developercertificate.org/).

## License

Apache License 2.0. See [LICENSE](LICENSE).