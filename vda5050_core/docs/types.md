# VDA5050 Types and Serialization

This guide shows how to create VDA5050 messages in C++ and serialize them to and from JSON using `vda5050_core`.

## Overview

`vda5050_core` provides C++ types for common VDA5050 messages, including:

- `Order`
- `State`
- `InstantActions`
- `Connection`
- `Factsheet`
- `Visualization`

These types can be constructed directly in C++ and converted to JSON for communication, testing, logging or storage.

## Deserializing an Incoming Message

The following example converts an incoming JSON payload into an `Order`.

```cpp
#include <nlohmann/json.hpp>

#include "vda5050_core/json_utils/serialization.hpp"
#include "vda5050_core/types/order.hpp"

const std::string payload = R"({
  "headerId": 1,
  "timestamp": "2026-07-14T10:30:00.000Z",
  "version": "2.0.0",
  "manufacturer": "MyCompany",
  "serialNumber": "AGV-001",
  "orderId": "order-001",
  "orderUpdateId": 0,
  "nodes": [
    {
      "nodeId": "start",
      "sequenceId": 0,
      "released": true,
      "actions": [],
      "nodePosition": {
        "x": 0.0,
        "y": 0.0,
        "theta": 0.0,
        "mapId": "map1"
      }
    }
  ],
  "edges": []


})";

try
{
  const nlohmann::json json_order = nlohmann::json::parse(payload);
  const auto order = json_order.get<vda5050_core::types::Order>();

  // Access the deserialized C++ fields.
  std::cout << order.order_id << '\n';
}
```

Parsing checks that the input is valid JSON.

## Serializing to JSON

The following examples show

Include the serialization header and assign the C++ value to `nlohmann::json`. The conversion uses the VDA5050 JSON field names, such as `orderId`, `sequenceId`, and `nodePosition`.

```cpp
#include <iostream>

#include <nlohmann/json.hpp>

#include "vda5050_core/json_utils/serialization.hpp"
#include "vda5050_core/types/order.hpp"

nlohmann::json json_order = order;

// Compact JSON, suitable for transport:
const std::string payload = json_order.dump();

// Human-readable JSON, useful for logs and debugging:
std::cout << json_order.dump(2) << '\n';
```

The serialized output uses VDA5050 JSON field names such as:

```text
orderId
orderUpdateId
sequenceId
nodePosition
serialNumber
```

Fields represented by an empty `std::optional` are normally omitted from the JSON output.

Conversion to a VDA5050 type may fail when:

- a required field is missing;
- a field has an incompatible JSON type; or
- a value cannot be converted to the corresponding C++ type.

