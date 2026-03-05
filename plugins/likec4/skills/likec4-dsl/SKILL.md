---
name: writing-likec4
description: >
  Provides complete LikeC4 DSL syntax reference for writing .likec4 and .c4 files.
  Covers specification blocks, model definitions, views, predicates, dynamic views,
  deployment models, styling properties, and CLI commands. Use when writing, editing,
  or generating LikeC4 DSL code, working with likec4 syntax, element kinds,
  relationships, view predicates, or running likec4 CLI tools.
---

# LikeC4 DSL Reference

Write correct LikeC4 DSL code. Files use `.likec4` or `.c4` extensions. All source files in a project merge into a single unified model.

## Recommended Project Structure

Organize LikeC4 files following C4 decomposition:

```
architecture/
├── specification.likec4
├── models/
│   └── <system-name>/
│       ├── context.likec4              # Level 1: actors, systems
│       └── containers/
│           └── <container-name>/
│               ├── container.likec4    # Level 2: container definition
│               └── components/
│                   └── *.likec4        # Level 3: component definitions
├── views/
│   ├── context/                        # Level 1 views
│   ├── containers/                     # Level 2 views
│   ├── components/                     # Level 3 views
│   ├── deployment/                     # Deployment views
│   └── dynamic/                        # Dynamic/sequence views
└── deployment/
    └── model.likec4                    # Deployment nodes and instances
```

## Top-Level Blocks

Every `.likec4` file contains one or more of these blocks. Multiple blocks of the same type are allowed across files.

### specification

Define element kinds, relationship kinds, tags, and colors used throughout the model.

```likec4
specification {
  element actor {
    style {
      shape person
      color secondary
    }
  }
  element system
  element container
  element component

  relationship async {
    style {
      line dashed
      color muted
    }
  }
  relationship subscribes

  tag deprecated
  tag next {
    color green
  }

  color custom-blue #3B82F6
}
```

**Element kind properties:** title, description, technology, notation, style
**Relationship kind properties:** style (line, color, head, tail)

### model

Define architectural elements, their hierarchy, and relationships.

```likec4
model {
  actor customer = actor 'Customer' {
    description 'A user of the online banking system'
  }

  system onlineBanking = system 'Online Banking' {
    description 'Allows customers to view accounts and make payments'
    #next

    container webApp = container 'Web Application' {
      technology 'React, TypeScript'
      description 'Delivers the banking experience to customers'

      component auth = component 'Auth Module' {
        technology 'OAuth2'
      }
      component dashboard = component 'Dashboard' {
        technology 'React'
      }

      auth -> dashboard 'Provides identity to'
    }

    container api = container 'API' {
      technology 'Spring Boot, Java'
    }

    container db = container 'Database' {
      technology 'PostgreSQL'
      style { shape storage }
    }

    webApp -> api 'Makes API calls using JSON/HTTPS'
    api -> db 'Reads from and writes to using JDBC'
    api -> emailSystem 'Sends confirmation emails using SMTP'
  }

  system emailSystem = system 'Email System' {
    description 'Sends transactional emails'
    style { color muted }
  }

  customer -> onlineBanking 'Views accounts and makes payments'
  onlineBanking -> emailSystem 'Sends notification emails to'
}
```

**Element properties:**
- `title` or inline string: Display name
- `description`: Detail text (supports markdown with triple quotes `'''`)
- `summary`: Brief overview
- `technology`: Implementation stack (auto-derived from bundled icons)
- `link`: URLs (`link https://example.com 'Label'`)
- `metadata`: Key-value pairs (`metadata { version '2.0' }`)
- Tags: `#tagname` syntax

**Naming rules:** Letters, digits, hyphens, underscores. Cannot start with digit or contain periods.

**Hierarchy:** Nesting creates parent-child relationships. Fully qualified names use dots: `onlineBanking.webApp.auth`

**Relationships:**
- Basic: `source -> target 'label'`
- Kinded (bracket): `source -[async]-> target 'label'`
- Kinded (dot): `source .subscribes target 'label'`
- Sourceless (parent as source): `-> target 'label'`
- Self-reference: `it` or `this` refers to containing element

**Relationship properties:** title, description, technology, tags, links, metadata, navigateTo

### views

Create visualizations of the architecture model.

```likec4
views {
  view index {
    title 'System Landscape'
    include *
  }

  view of onlineBanking {
    title 'Online Banking - Containers'
    include *
    include customer
    include emailSystem
    style db { color amber }
    autoLayout TopBottom
  }

  view bankingComponents of onlineBanking.webApp {
    title 'Web App Components'
    include *
    include onlineBanking.api
    autoLayout TopBottom
  }
}
```

**View types:**
- `view <name>` - standalone view
- `view <name> of <element>` - scoped to element (predicates resolve within scope)
- `view index` - default/landing view
- `dynamic view <name>` - step-by-step interaction flow
- `deployment view <name>` - deployment topology

**View properties:** title, description, tags, links

**Auto-layout directions:** TopBottom, BottomTop, LeftRight, RightLeft

**View extension:** `view child extends parent { ... }` inherits predicates and styles

### Element Predicates

Control which elements appear in views:

```likec4
include cloud                        // specific element
include *                            // top-level children (or scoped children)
include cloud.*                      // direct children of cloud
include cloud.**                     // all descendants of cloud
include cloud._                      // children with relationships only
include backend with { color amber } // override style
include * where kind is container    // filter by kind
exclude * where tag is #deprecated   // exclude by tag
```

### Relationship Predicates

Include elements based on connections:

```likec4
include customer -> cloud            // directed relationship
include customer <-> cloud           // any direction
include -> backend                   // incoming to backend
include cloud.* ->                   // outgoing from children
include -> cloud.* ->               // nested elements with relationships
```

**Filtering with where:**
```likec4
include cloud.* where kind is microservice
exclude * where tag is not #v1
include * -> * where source.tag is #next and target.kind is database
```

**Logical operators:** `and`, `or`, `not`, `is`, `is not`

### Groups

Visual boundaries around elements in views:

```likec4
views {
  view index {
    group 'Frontend' {
      include webApp, mobileApp
      style { color indigo }
    }
    group 'Backend' {
      include api, worker
    }
  }
}
```

### Dynamic Views

Describe interaction scenarios with ordered steps:

```likec4
views {
  dynamic view checkoutFlow {
    title 'Checkout Flow'

    customer -> webApp 'Initiates checkout'
    webApp -> api 'Sends order details using JSON/HTTPS'
    api -> db 'Stores order data using JDBC'
    webApp <- api 'Returns order confirmation'
    webApp -> customer 'Displays order summary'

    api -> emailSystem {
      title 'Sends confirmation email'
      notes '''
        Triggers async email delivery.
        Customer receives confirmation within 5 minutes.
      '''
    }
  }
}
```

**Dynamic view features:**
- Chained steps: `A -> B -> C -> D`
- Reverse: `A <- B 'response'`
- Parallel: `parallel { ... }`
- Notes: markdown documentation on steps
- NavigateTo: link to other views
- Self-calls: `api -> api 'process request'`

### Deployment Model

Define physical topology separately from logical model:

```likec4
specification {
  deploymentNode environment
  deploymentNode zone
  deploymentNode vm
  deploymentNode k8s
}

deployment {
  environment prod {
    zone eu {
      k8s cluster1 {
        instanceOf onlineBanking.api {
          title 'API (EU)'
          style { multiple true }
        }
        instanceOf onlineBanking.webApp
      }
      vm dbServer {
        instanceOf onlineBanking.db {
          title 'Primary DB'
          technology 'PostgreSQL 16'
        }
      }
    }
    zone us {
      vm dbReplica {
        db = instanceOf onlineBanking.db {
          title 'Read Replica'
        }
      }
      // Deployment-specific relationship
      dbReplica.db -> eu.dbServer 'Replicates from'
    }
  }
}
```

**Deployment views:**
```likec4
views {
  deployment view prodDeployment {
    title 'Production Deployment'
    include prod.**
    include * where tag is #next
  }
}
```

### Styling

**Element shapes:** rectangle (default), component, storage, cylinder, browser, mobile, person, queue, bucket, document

**Theme colors:** primary (default), secondary, muted, amber, gray, green, indigo, red

**Sizes:** xsmall/xs, small/sm, medium/md (default), large/lg, xlarge/xl
- Applies to: size, padding, textSize, iconSize

**Element style properties:**
```likec4
style {
  shape cylinder
  color green
  icon tech:postgresql
  iconPosition top       // left (default), right, top, bottom
  iconColor indigo
  iconSize lg
  size lg
  padding sm
  textSize md
  opacity 60%            // for container boundaries
  border dashed          // dashed (default), dotted, solid, none
  multiple true          // show as stacked copies
}
```

**Relationship style properties:**
```likec4
style {
  line dashed            // dashed (default), solid, dotted
  color muted
  head normal            // normal, onormal, diamond, odiamond, crow, vee, open, none
  tail none
}
```

**Icon packs:** `aws:`, `azure:`, `bootstrap:`, `gcp:`, `tech:`

**In-view styling:**
```likec4
views {
  view index {
    include *
    style cloud.* { color green }
    style * where tag is #deprecated { color gray; opacity 30% }
  }
}
```

## Global Block

Define reusable predicates and styles:

```likec4
global {
  predicates {
    hide-deprecated {
      exclude * where tag is #deprecated
    }
  }
  style {
    element * where tag is #deprecated {
      color gray
      opacity 30%
    }
  }
}
```

## CLI Commands

**Development:**
- `likec4 serve` / `likec4 dev` - Start dev server with hot-reload
- `likec4 validate` - Check syntax errors

**Build:**
- `likec4 build -o ./dist` - Build static website
- `likec4 build --output-single-file` - Self-contained HTML

**Export:**
- `likec4 export png -o ./assets` - Export PNG images
- `likec4 export json -o dump.json` - Export model as JSON
- `likec4 export drawio -o ./diagrams` - Export to DrawIO

**Code generation:**
- `likec4 gen mermaid` / `likec4 gen dot` / `likec4 gen d2` / `likec4 gen plantuml`
- `likec4 gen react` / `likec4 gen webcomponent`

**MCP server:**
- `likec4 mcp` - Start MCP server (stdio or HTTP transport)

**Install:** `npm i -D likec4` or `npx likec4 [command]`

## References

- `references/style-reference.md` - Complete styling properties
- `references/predicate-reference.md` - All predicate patterns
- `examples/complete-project.likec4` - Full working example
