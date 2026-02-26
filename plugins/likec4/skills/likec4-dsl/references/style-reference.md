# LikeC4 Style Reference

## Element Shapes

| Shape | Use For |
|-------|---------|
| `rectangle` | Default. Generic elements, systems. |
| `person` | Actors, users, roles |
| `component` | Software components |
| `storage` | Databases, data stores |
| `cylinder` | Databases (alternative to storage) |
| `browser` | Web applications, SPAs |
| `mobile` | Mobile applications |
| `queue` | Message queues, event buses |
| `bucket` | Object storage, file systems |
| `document` | Documents, files, configs |

## Theme Colors

| Color | Typical Use |
|-------|-------------|
| `primary` | Default. Main system elements. |
| `secondary` | Supporting elements |
| `muted` | External systems, de-emphasized elements |
| `amber` | Warnings, databases, storage |
| `gray` | Deprecated, inactive elements |
| `green` | Healthy, new, approved elements |
| `indigo` | Frontend, UI elements |
| `red` | Errors, critical, security elements |

## Custom Colors

Define in specification block:

```likec4
specification {
  color brand-blue #3B82F6
  color brand-dark #1E293B
  color success rgb(34 197 94)
  color warning rgba(245 158 11 80%)
}
```

Supported formats: `#RGB`, `#RRGGBB`, `#RRGGBBAA`, `rgb(r g b)`, `rgba(r g b a%)`

## Size Scale

All size properties accept: `xsmall`/`xs`, `small`/`sm`, `medium`/`md` (default), `large`/`lg`, `xlarge`/`xl`

| Property | Controls |
|----------|----------|
| `size` | Overall element dimensions |
| `padding` | Space around title text |
| `textSize` | Font size of element title |
| `iconSize` | Icon dimensions |

## Icon Packs

Reference icons with `pack:name` syntax:

| Pack | Examples |
|------|----------|
| `tech:` | `tech:react`, `tech:postgresql`, `tech:docker`, `tech:kafka` |
| `aws:` | `aws:lambda`, `aws:s3`, `aws:rds`, `aws:sqs` |
| `azure:` | `azure:app-service`, `azure:sql-database` |
| `gcp:` | `gcp:cloud-run`, `gcp:cloud-sql` |
| `bootstrap:` | `bootstrap:gear`, `bootstrap:shield-lock` |

When using bundled icons, LikeC4 auto-derives the `technology` label.

## Relationship Line Styles

| Property | Values |
|----------|--------|
| `line` | `dashed` (default), `solid`, `dotted` |
| `color` | Any theme or custom color |
| `head` | `normal`, `onormal`, `diamond`, `odiamond`, `crow`, `vee`, `open`, `none` |
| `tail` | Same as head values |

## Border Styles (Containers/Groups)

| Value | Use |
|-------|-----|
| `dashed` | Default container boundary |
| `dotted` | Lighter boundary |
| `solid` | Strong boundary |
| `none` | No visible boundary |

## Opacity

Apply to container/group elements as percentage: `opacity 60%`

## Multiple Instances

Show element as stacked copies: `multiple true`

Useful for: load-balanced services, replicated databases, worker pools.
