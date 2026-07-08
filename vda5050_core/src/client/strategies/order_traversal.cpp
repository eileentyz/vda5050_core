/*
 * Copyright (C) 2026 ROS-Industrial Consortium Asia Pacific
 * Advanced Remanufacturing and Technology Centre
 * A*STAR Research Entities (Co. Registration No. 199702110H)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "vda5050_core/client/strategies/order_traversal.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>

#include "vda5050_core/client/events/navigate_to_node.hpp"
#include "vda5050_core/client/resources/order_execution.hpp"
#include "vda5050_core/client/updates/node_reached.hpp"
#include "vda5050_core/execution/event_queue.hpp"
#include "vda5050_core/logger/logger.hpp"
#include "vda5050_core/types/edge.hpp"
#include "vda5050_core/types/node.hpp"

namespace vda5050_core {

namespace client {

namespace {

// Request a new base when this few released nodes remain.
constexpr std::size_t kLowBaseThreshold = 1;

// Navigation target and its incoming edge.
struct Dispatch
{
  types::NodeState target;
  std::optional<types::EdgeState> via_edge;
};

// Updates the state when a node is reached.
// Returns false if the node is unknown, already handled, or out of order.
bool advance_to_reached(types::State& state, const NodeReachedUpdate& reached)
{
  // Find the reached node in the current base.
  auto node_it = std::find_if(
    state.node_states.begin(), state.node_states.end(),
    [&](const types::NodeState& n) {
      return n.sequence_id == reached.sequence_id &&
             n.node_id == reached.node_id;
    });
  if (node_it == state.node_states.end())
  {
    return false;
  }

  // Only accept the next expected node.
  const bool is_next_expected = std::none_of(
    state.node_states.begin(), state.node_states.end(),
    [&](const types::NodeState& n) {
      return n.sequence_id < reached.sequence_id;
    });
  if (!is_next_expected) return false;

  // Update last reached node and remove it from pending state.
  state.last_node_id = reached.node_id;
  state.last_node_sequence_id = reached.sequence_id;
  state.node_states.erase(node_it);

  // Remove the incoming edge.
  if (reached.sequence_id > 0)
  {
    const uint32_t incoming_edge_seq = reached.sequence_id - 1;
    state.edge_states.erase(
      std::remove_if(
        state.edge_states.begin(), state.edge_states.end(),
        [&](const types::EdgeState& e) {
          return e.sequence_id == incoming_edge_seq;
        }),
      state.edge_states.end());
  }

  return true;
}

// Updates new_base_request from the base ahead of the last reached node.
void refresh_new_base_request(types::State& state)
{
  const bool anything_ahead = std::any_of(
    state.node_states.begin(), state.node_states.end(),
    [&](const types::NodeState& n) {
      return n.sequence_id > state.last_node_sequence_id;
    });
  if (!anything_ahead)
  {
    state.new_base_request = std::nullopt;
    return;
  }

  const std::size_t released_ahead = static_cast<std::size_t>(std::count_if(
    state.node_states.begin(), state.node_states.end(),
    [&](const types::NodeState& n) {
      return n.released && n.sequence_id > state.last_node_sequence_id;
    }));
  state.new_base_request = released_ahead <= kLowBaseThreshold;
}

// Finds the next node after the last reached node.
// Returns nullopt if there is no node ahead or the next node is still horizon.
std::optional<Dispatch> compute_next_dispatch(
  const types::State& state, std::size_t& next_node_index)
{
  const types::NodeState* next = nullptr;
  if (next_node_index >= state.node_states.size())
  {
    next_node_index = 0;
  }

  for (std::size_t i = next_node_index; i < state.node_states.size(); ++i)
  {
    const auto& node = state.node_states[i];
    if (node.sequence_id <= state.last_node_sequence_id)
    {
      continue;
    }
    next_node_index = i;
    next = &node;
    break;
  }
  if (next == nullptr) return std::nullopt;  // No node ahead.

  // Stop before the horizon.
  if (!next->released) return std::nullopt;

  // Find the edge to the next node.
  std::optional<types::EdgeState> via_edge;
  if (next->sequence_id > 0)
  {
    const uint32_t via_seq = next->sequence_id - 1;
    auto edge_it = std::find_if(
      state.edge_states.begin(), state.edge_states.end(),
      [&](const types::EdgeState& e) { return e.sequence_id == via_seq; });
    if (edge_it != state.edge_states.end()) via_edge = *edge_it;
  }

  return Dispatch{*next, std::move(via_edge)};
}

types::Node to_node(const types::NodeState& state)
{
  types::Node node;
  node.node_id = state.node_id;
  node.sequence_id = state.sequence_id;
  node.released = state.released;
  node.node_position = state.node_position;
  node.node_description = state.node_description;
  return node;
}

types::Edge to_edge(const types::EdgeState& state)
{
  types::Edge edge;
  edge.edge_id = state.edge_id;
  edge.sequence_id = state.sequence_id;
  edge.released = state.released;
  edge.edge_description = state.edge_description;
  edge.trajectory = state.trajectory;
  return edge;
}

}  // namespace

OrderTraversal::OrderTraversal() = default;

void OrderTraversal::init(
  std::shared_ptr<execution::ContextInterface> /*context*/)
{
  // Nothing to initialise; node-reached signals are read from the context.
}

void OrderTraversal::step(std::shared_ptr<execution::ContextInterface> context)
{
  if (!context) return;

  auto execution = context->get_resource<OrderExecutionResource>();
  if (!execution) return;

  // Only run traversal while an order is active.
  if (!execution->is_executing_order()) return;

  auto reached = context->get_update<NodeReachedUpdate>();

  types::State state = execution->get_state();

  // Apply each cached node-reached update only once.
  bool state_changed = false;
  if (reached && reached != last_processed_)
  {
    state_changed = advance_to_reached(state, *reached);
    last_processed_ = reached;
  }

  // Check every step so base extensions can resume traversal.
  const std::optional<bool> prev_request = state.new_base_request;
  refresh_new_base_request(state);
  if (state.new_base_request != prev_request) state_changed = true;

  const std::string order_id = state.order_id;
  if (
    next_node_order_id_ != state.order_id ||
    next_node_order_update_id_ != state.order_update_id)
  {
    next_node_index_ = 0;
    next_node_order_id_ = state.order_id;
    next_node_order_update_id_ = state.order_update_id;
  }

  std::optional<Dispatch> dispatch =
    compute_next_dispatch(state, next_node_index_);

  if (state_changed) execution->set_state(std::move(state));

  if (!dispatch) return;

  if (
    last_dispatched_seq_ == dispatch->target.sequence_id &&
    last_dispatched_order_id_ == order_id)
  {
    return;
  }
  last_dispatched_seq_ = dispatch->target.sequence_id;
  last_dispatched_order_id_ = order_id;

  auto target = adapter::NodeRequest::from_node(to_node(dispatch->target));
  std::optional<adapter::EdgeRequest> via_edge;
  if (dispatch->via_edge)
  {
    via_edge = adapter::EdgeRequest::from_edge(to_edge(*dispatch->via_edge));
  }

  engine()->emit<NavigateToNodeEvent>(
    execution::Priority::NORMAL, std::move(target), std::move(via_edge));

  engine()->step();
}

}  // namespace client
}  // namespace vda5050_core
