# LikeC4 DSL cheatsheet (constrained to orthodox C4 usage)

A LikeC4 project = a folder of `.c4` files merged into one model (order-independent). Blocks: `specification`, `model`, `views`, `deployment`, `global`. For the project's file/folder layout — `shared/_spec.c4`, `models/`, `views/`, `dynamic_views/`, one element per file via `extend` — see `methodology.md` § File layout; this cheatsheet covers only the DSL syntax that goes *inside* those files.

## Elements

```likec4
model {
  // kind name 'Title' — or: name = kind 'Title' ['summary'] ['technology']
  customer = person 'Personal Banking Customer' 'A customer of the bank with personal accounts'

  internetBanking = softwareSystem 'Internet Banking System' {
    description 'Lets customers view accounts and make payments'

    webApp = webapp 'Single-Page Application' {
      technology 'TypeScript, React'
      description 'Banking UI running in the browser'
    }

    apiApp = container 'API Application' {
      technology 'Java, Spring Boot'
      description 'Serves the banking API over JSON/HTTPS'

      signinCtrl = component 'Sign-In Controller' {
        technology 'Spring MVC REST Controller'
        description 'Allows users to sign in'
      }
    }

    db = database 'Database' {
      technology 'PostgreSQL'
      description 'Stores user credentials, accounts, transactions'
    }
  }

  mainframe = externalSystem 'Mainframe Banking System' {
    #external
    description 'Stores core banking information'
  }
}
```

- Names: letters/digits/`-`/`_`, no leading digit, no `.`. Nested elements get dotted FQNs: `internetBanking.apiApp.signinCtrl`. Names must be unique within a parent.
- Tags (`#tag`) must come FIRST inside an element body, before other properties.
- `summary` = short text shown on the diagram; `description` = long form (markdown via `'''...'''`) shown in the details pane. If only `description` exists it's shown on the diagram.
- Extra properties available: `link <url> ['label']`, `metadata { key 'value' }`, per-element `style { }` (avoid — style via the spec kinds so the legend stays truthful).
- `icon tech:react` / `aws:s3` / `gcp:...` / `azure:...` adds a logo (and auto-derives the technology label if none set).

## Relationships

```likec4
model {
  // source -> target 'title', then a nested block for everything else.
  // ⚠️ TRAP: a second inline string is the DESCRIPTION, not technology
  // (`a -> b 'title' 'HTTPS'` puts HTTPS in the description field).
  // ALWAYS set technology via the nested property; it can't be misread:
  customer -> internetBanking.webApp 'views balances and makes payments using' {
    technology 'HTTPS'
  }

  // Re-opening an element defined elsewhere (or earlier) requires `extend`:
  extend internetBanking {
    webApp -> apiApp 'makes API calls to' {
      technology 'JSON/HTTPS'
    }
    apiApp -> db 'reads from and writes to' {
      technology 'JDBC'
    }

    // nested sugar (use sparingly; explicit source is clearer):
    // inside an element body: `-> x 'title'` means <parent> -> x
    // `it -> x` / `this -> x` also refer to the parent
  }
  // (Relationships declared inside the ORIGINAL element body need no extend.)
  // Unique nested names resolve from top level too: `apiApp -> mainframe ...`

  // async kind from the canonical spec (dotted line):
  apiApp -[async]-> reportingQueue 'publishes transaction events to' {
    technology 'Kafka'
  }
  // equivalent kind syntax: apiApp .async reportingQueue 'publishes...'
}
```

- ONLY `->` in the model (unidirectional). `<->` is legal LikeC4 but banned by this skill outside view predicates.
- Nested block form allows `title`, `description`, `technology`, `link`, `metadata`, `navigateTo <dynamicViewName>` (click-through to a scenario).

## Views

Views are projections of the model built from ordered `include`/`exclude` predicates (later predicates see earlier results; excludes only remove what was already included).

### Canonical C4 view patterns

```likec4
views {
  // SYSTEM LANDSCAPE (only if >1 system): top-level people + systems
  view index {
    title 'System Landscape — Big Bank plc'
    include *            // unscoped * = all top-level elements
  }

  // SYSTEM CONTEXT: system as black box + direct neighbors.
  // List them explicitly — `include *` + `exclude sys.*` does NOT work
  // (excluding children also drops neighbors pulled in via child relationships).
  view context of internetBanking {
    title 'System Context — Internet Banking System'
    include internetBanking, customer, mainframe, email
  }

  // CONTAINER VIEW: inside one system, one level down
  view containers of internetBanking {
    title 'Containers — Internet Banking System'
    include *            // system boundary + its containers + connected externals
  }

  // COMPONENT VIEW: inside one container
  view apiComponents of internetBanking.apiApp {
    title 'Components — API Application'
    include *
  }
}
```

`view <name> of <element>` scopes the view (unqualified references resolve inside the element) and becomes that element's drill-down target on click. `index` is the default view rendered when none is specified.

### Useful predicate tools (keep views single-level!)

```likec4
include a, b, c              // comma-combine
include sys.*                // children
include sys.**               // all descendants — level-mixing risk, avoid
include -> sys, sys ->       // elements with incoming / outgoing rels to visible ones
include * where tag is not #deprecated
exclude * -> * where tag is #planned
include sys with { navigateTo containers }   // per-view override/navigation
include a -> b with { title 'sends X to' }   // fix merged '[...]' edge labels
autoLayout LeftRight         // TopBottom (default) | BottomTop | RightLeft
```

`group 'Title' { include ... }` draws a boundary box — for visual grouping only, never as a fake abstraction level.

### Dynamic views (scenarios)

```likec4
views {
  dynamic view signIn {
    title 'Dynamic — Customer signs in'
    // Dynamic views are UNSCOPED: always use fully qualified names.
    // Steps take a single 'title' string only — put protocols in the title.
    customer -> internetBanking.webApp 'enters credentials into'
    internetBanking.webApp -> internetBanking.apiApp 'POSTs /signin over JSON/HTTPS to'
    internetBanking.apiApp -> internetBanking.db 'validates credentials, over JDBC, against'
    internetBanking.webApp <- internetBanking.apiApp 'returns auth token to'  // reverse allowed
    include internetBanking                     // show the boundary
  }
}
```

Steps in declaration order; `parallel { }` / `opt 'title' { }` / `loop 'title' { }` blocks available. Keep all steps at ONE abstraction level (usually containers).

## Deployment (when asked)

```likec4
deployment {
  environment prod 'Production' {
    zone aws 'AWS us-east-1' {
      node ecs 'ECS Cluster' {
        instanceOf internetBanking.apiApp   // deploys a model element
      }
      node rds 'RDS' {
        instanceOf internetBanking.db
      }
    }
  }
}
views {
  deployment view prodDeployment {
    title 'Deployment — Production'
    include **
  }
}
```

(The required `deploymentNode` kinds — `environment`, `zone`, `node` — are already declared in canonical-spec.c4.)

## CLI

```bash
npx likec4 validate .            # parse + model check — must pass
npx likec4 export png -o ./out   # render all views (needs Playwright browser)
npx likec4 start                 # local interactive preview
npx likec4 gen mermaid|plantuml|dot|d2   # convert if user wants another format
```
