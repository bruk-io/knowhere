# LikeC4 Predicate Reference

Predicates control which elements and relationships appear in views. Order matters - predicates apply sequentially.

## Element Selectors

| Predicate | Selects |
|-----------|---------|
| `include element` | Specific element by name |
| `include *` | All top-level elements (or scoped children) |
| `include cloud.*` | Direct children of cloud |
| `include cloud.**` | All descendants of cloud |
| `include cloud._` | Children of cloud that have relationships |

## Relationship Selectors

| Predicate | Selects |
|-----------|---------|
| `include A -> B` | Directed relationship from A to B |
| `include A <-> B` | Relationship in either direction |
| `include -> B` | All incoming relationships to B |
| `include A ->` | All outgoing relationships from A |
| `include -> B ->` | Incoming and outgoing from B |

## Where Clauses

Filter elements by properties:

```likec4
include * where kind is container
include * where kind is not component
include * where tag is #next
include * where tag is not #deprecated
```

Combine with logical operators:

```likec4
include * where kind is container and tag is #next
include * where tag is #v1 or tag is #v2
include * where not (tag is #deprecated)
```

Filter relationship endpoints:

```likec4
include * -> * where source.kind is service
include * -> * where target.tag is #deprecated
include * -> * where source.tag is #next and target.kind is database
```

## Style Overrides

Apply styles inline with `with`:

```likec4
include backend with { color amber }
include db with { color red; shape cylinder }
include api with { navigateTo apiDetails }
```

Style by selector:

```likec4
style cloud.* { color green }
style * where tag is #deprecated { color gray; opacity 30% }
```

## Exclude

Remove elements or relationships:

```likec4
include *
exclude messageBroker
exclude * where tag is #internal
```

## Groups

Visual grouping in views:

```likec4
group 'Frontend Services' {
  include webApp, mobileApp
  color indigo
}
```

## Auto-Layout

| Direction | Description |
|-----------|-------------|
| `autoLayout TopBottom` | Top to bottom (default) |
| `autoLayout BottomTop` | Bottom to top |
| `autoLayout LeftRight` | Left to right |
| `autoLayout RightLeft` | Right to left |

## Rank Constraints

Align elements on the same rank:

```likec4
rank same { webApp, mobileApp }
rank source { customer }
rank sink { database }
```

## Global Predicates

Define reusable predicate sets:

```likec4
global {
  predicates {
    hide-deprecated {
      exclude * where tag is #deprecated
    }
    show-next {
      include * where tag is #next
      style * where tag is #next { color green }
    }
  }
}
```

Apply in views:

```likec4
views {
  view index {
    include *
    extend hide-deprecated
  }
}
```
