# Authority and Discovery Layering

Keep intent compact at the outer layers and mechanics canonical at the
deepest applicable layer. Link inward instead of copying procedures outward.

## Rule

Every layered asset type in this platform — instructions, skills, contracts,
and operating docs alike — has exactly one canonical, deepest-applicable
source. Shallower layers state intent and point inward; they do not restate
or fork the mechanics. This keeps authority singular and keeps it
discoverable: an agent or human can start at any outer layer and always find
one place, not several drifting copies, where the real rule lives.

Copying a procedure outward instead of linking to it creates a second
authority. The two copies then drift, and nothing in the repository can say
which one is current.

## Existing instances

- [Agent Context Routing](../../platform/agent-control-plane/agent-assets/instructions/agent-context-routing.md)
  applies this to instruction and skill discovery: root entrypoints stay
  thin, canonical skill and instruction bodies live under
  `agent-assets/`, and runtime adapters reference or translate rather than
  duplicate.
- [Governed Repository Delivery](../operations/governed-repository-delivery.md)
  applies this to the delivery workflow: the operations doc owns the human
  operating model, and named deeper layers (branching mechanics, shaping,
  Jira/Git skills, hooks) own their own narrower mechanics.
