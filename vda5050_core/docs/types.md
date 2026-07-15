# vda5050_core::types and vda5050_core::json_utils

This document explains how `vda5050_core` converts VDA5050 message types to and from JSON.

## 1. Overview

The library keeps the VDA5050 data types separate from the JSON conversion code.

- The `vda5050_core::types` namespace contains C++ structs that represent VDA5050 messages.
- The `vda5050_core::json_utils` namespace provides functions that convert these structs to and from JSON.

```cpp
#include "vda5050_core/types/order.hpp"           // struct only
#include "vda5050_core/json_utils/serialization.hpp"  // adds JSON
```

This separation allows the VDA5050 types to be used without requiring JSON support. The JSON conversion uses `nlohmann::json`. After including the serialization header, VDA5050 types can be converted directly.

```cpp
using namespace vda5050_core;

types::Order order;
order.order_id = "order_1";
order.order_update_id = 0;

// Serialize
nlohmann::json j = order;
std::string payload = j.dump();

// Deserialize
types::Order parsed = nlohmann::json::parse(payload);
```

`ProtocolAdapter` uses the same JSON conversion internally. This means that `publish<T>()` and `subscribe<T>()` do not need a separate serializer.

## 2. Naming Convention

The VDA5050 specification uses `lowerCamelCase` for JSON field names. The C++ types use `snake_case` . The serializer converts between the two naming styles.


| C++                    | JSON           |
| ---------------------- | -------------- |
| `order.order_id`       | `orderId`      |
| `action.blocking_type` | `blockingType` |
| `state.agv_position`   | `agvPosition`  |


The JSON field names must follow the VDA5050 specification.

## 3. Create and Serialize an Order

This complete example creates an order with two nodes and one edge, converts it to JSON, and converts it back to the strongly typed C++ representation `Order`:

```cpp
#include <chrono>
#include <iostream>
#include <string>

#include <nlohmann/json.hpp>

#include "vda5050_core/json_utils/serialization.hpp"
#include "vda5050_core/types/order.hpp"

int main()
{
  using vda5050_core::types::Edge;
  using vda5050_core::types::Node;
  using vda5050_core::types::NodePosition;
  using vda5050_core::types::Order;

  Order order{};
  order.header.header_id = 1;
  order.header.timestamp = std::chrono::system_clock::now();
  order.header.version = "2.0.0";
  order.header.manufacturer = "MyCompany";
  order.header.serial_number = "AGV-001";
  order.order_id = "order-001";
  order.order_update_id = 0;

  Node start{};
  start.node_id = "start";
  start.sequence_id = 0;
  start.released = true;
  start.node_position = NodePosition{};
  start.node_position->x = 0.0;
  start.node_position->y = 0.0;
  start.node_position->theta = 0.0;
  start.node_position->map_id = "map1";

  Node goal{};
  goal.node_id = "goal";
  goal.sequence_id = 2;
  goal.released = true;
  goal.node_position = NodePosition{};
  goal.node_position->x = 5.0;
  goal.node_position->y = 2.0;
  goal.node_position->map_id = "map1";

  Edge route{};
  route.edge_id = "start-to-goal";
  route.sequence_id = 1;
  route.start_node_id = start.node_id;
  route.end_node_id = goal.node_id;
  route.released = true;

  order.nodes = {start, goal};
  order.edges = {route};

  // Serialize to a JSON value and then to a compact string.
  const nlohmann::json json_order = order;
  const std::string payload = json_order.dump();

  // Use dump(2) for indented, human-readable output.
  std::cout << json_order.dump(2) << std::endl;

  // Deserialize the payload and verify the round trip.
  const Order decoded = nlohmann::json::parse(payload).get<Order>();
  return decoded == order ? 0 : 1;
}
```

Assigning a VDA5050 type to `nlohmann::json` calls the repository serializers. Use `dump()` for compact transport data and `dump(2)` for readable logs.

## 4. Deserialize an Incoming Payload

To deserialize an incoming JSON string, parse the JSON text first into a `nlohmann::json` object, then convert it to the expected VDA5050 type with `get<T>()`:

```cpp
#include <iostream>
#include <string>

#include <nlohmann/json.hpp>

#include "vda5050_core/json_utils/serialization.hpp"
#include "vda5050_core/types/order.hpp"

void handle_order_payload(const std::string& payload)
{
  try
  {
    const nlohmann::json data = nlohmann::json::parse(payload);
    const auto order = data.get<vda5050_core::types::Order>();

    std::cout << "Received order: " << order.order_id << std::endl;
  }
  catch (const nlohmann::json::exception& error)
  {
    std::cerr << "Invalid order payload: " << error.what() << std::endl;
  }
}
```

`nlohmann::json::parse()` throws an exception when the JSON text is malformed. Converting with `get<T>()`can also throw when a required field is missing, a field has the wrong JSON type, or a timestamp or enum value cannot be converted.

## 5. Required and Optional Fields

The serializers read required fields with `json::at()`. For an `Order`, these include the header fields, `orderId`, `orderUpdateId`, `nodes`, and `edges`. If one of these fields is missing, deserialization throws an exception.

Optional C++ members use `std::optional`. An unset optional is omitted when the message is serialized. For example:

```cpp
vda5050_core::types::Order order{};
order.zone_set_id = "warehouse-zones";  // Produces "zoneSetId".
order.zone_set_id.reset();              // Omits "zoneSetId".
```

An empty array and an absent optional field are different. Required arrays such as `Order::nodes` and `Order::edges` are always serialized, even when empty.

## 6. JSON Conversion and Validation

Successful JSON conversion only means that the fields could be converted to the expected C++ types. It does not guarantees that the message follows every VDA5050 rule. For example, an order may deserialize successfully but still contain:

- Empty identifiers
- Invalid node or edge sequences
- Incorrect graph relationships
- Unsupported actions
- Conflicting action definitions

Use the validation library to check the message content:

```cpp
#include "vda5050_core/validation/content_validator.hpp"

const auto result =
  vda5050_core::validation::validate_order_content(order);
```

Additional validators are available under`vda5050_core/validation/` when graph structure, action conflicts, protocol limits, traversability, or master-side pre-send conditions also need to be checked.

## 7. CMake

The `json_utils` target provides the serialization utilities and includes the required message`types` and `nlohmann/json` dependencies.

```cmake
find_package(vda5050_core REQUIRED)

target_link_libraries(my_application
  PRIVATE
    vda5050_core::json_utils
)
```

If an application only constructs C++ message types and does not convert JSON, link `vda5050_core::types` instead.

