# VDA5050 Library and Support Tools

`vda5050_core` is a modern C++ library for developing AGV-side and master-control applications that communicate using the VDA5050 specification.

It provides reusable components for message handling, validation, MQTT communication, order execution, state reporting, and robot integration. The library is framework-independent and can be used in standalone C++ applications, ROS 2 systems, or existing robot software.

## Features

- VDA5050 message types in C++
- JSON serialization and deserialization
- Message validation
- MQTT transport
- Order and action execution
- Instant-action handling
- State reporting
- High-level client adapter API
- C++ examples and Python integration support

## Requirements

- C++
- ROS 2

## Build

From the root of the ROS 2 workspace:

```bash
colcon build --packages-select vda5050_core
source install/setup.bash
```

## Quick Start

Ensure that an MQTT broker is running on `localhost:1883`.

Start the C++ client adapter example:

```bash
ros2 run vda5050_core adapter_example
```

In another terminal, start the order publisher:

```bash
ros2 run vda5050_core order_publisher
```

The publisher  sends `factsheetRequest`, `stateRequest`, and `initPosition` before publishing a test order. It continues publishing order updates until the process is stopped.

## Documentation

Detailed guides are available under `[vda5050_core/docs/](vda5050_core/docs/README.md)`:


| Guide                                                              | Description                                                         |
| ------------------------------------------------------------------ | ------------------------------------------------------------------- |
| [Getting Started](vda5050_core/docs/getting-started.md)            | Building the library and running the example applications           |
| [Types and serialization](vda5050_core/docs/types.md)              | Creating VDA5050 message types and converting them to and from JSON |
| [Client adapter](vda5050_core/docs/adapter.md)                     | Connecting VDA5050 order handling to robot-specific software        |
| [Execution framework](vda5050_core/docs/execution.md)              | Lower-level execution strategies and contexts                       |
| [Architecture](vda5050_core/docs/design.md)                        | Architecture of `vda5050_core::execution`                           |
| [Migration from Open-RMF](vda5050_core/docs/migration-from-rmf.md) | Migrating from `rmf_fleet_adapter` to `vda5050_core`                |

## Examples
Runnable C++ examples are available under [Examples](vda5050_core/examples/), covering the client adapter, order publishing, and the execution framework. See [Getting Started](vda5050_core/docs/getting-started.md) for how to build and run them.

## Contributing
Contributions are welcome! All contributions are submitted under the Apache License 2.0.

Contributors must sign off each commit to certify compliance with the Developer Certificate of Origin:

```text
Signed-off-by: Your Name <your.email@example.com>
```

See [Contributing](vda5050_core/CONTRIBUTING.md)  for the full contribution guidelines.

## License

This project is licensed under the Apache License 2.0.