# Example Library Evaluation: date-fns vs dayjs vs moment

## Executive Summary

| Library | Score | Recommendation |
|---------|-------|----------------|
| date-fns | 4.3/5 | **Recommended** - Modern, tree-shakeable, actively maintained |
| dayjs | 4.1/5 | Good alternative - Small bundle, moment-compatible API |
| moment | 2.8/5 | **Avoid** - Legacy, in maintenance mode, large bundle |

---

## date-fns

### ThoughtWorks Radar Status
Not explicitly on radar, but "tree-shaking" and modular architecture are in **Adopt** ring.

### Health Metrics
- **Last commit:** 2 weeks ago
- **Last release:** 3 months ago (v3.x)
- **Open issues:** 156 (stable)
- **PR response:** ~1 week

### Repository Stats
```
Stars: 34.8k
Forks: 1.7k
Contributors: 400+
Weekly downloads: 25M+
```

### Dependencies
- Direct: 0 (zero dependencies!)
- Transitive: 0

### Security
- No known CVEs
- No npm audit warnings

### Bundle Size
- Tree-shakeable: Yes
- Per-function size: 200-800 bytes gzipped
- Full library: ~80kb minified (but you never import all)

### Documentation
- Comprehensive API docs
- Upgrade guides
- TypeScript built-in

### Score Breakdown
| Category | Score | Notes |
|----------|-------|-------|
| Activity | 5 | Very active development |
| Community | 4 | Large, helpful community |
| Dependencies | 5 | Zero dependencies! |
| Security | 5 | No issues |
| Documentation | 4 | Excellent |
| Performance | 4 | Tree-shakeable, efficient |
| **TOTAL** | **4.3** | |

---

## dayjs

### ThoughtWorks Radar Status
Not on radar. Alternative to moment.js.

### Health Metrics
- **Last commit:** 1 month ago
- **Last release:** 4 months ago
- **Open issues:** 800+ (concerning)
- **PR response:** Variable

### Repository Stats
```
Stars: 46.6k
Forks: 2.3k
Contributors: 200+
Weekly downloads: 18M+
```

### Dependencies
- Direct: 0
- Transitive: 0

### Security
- No known CVEs

### Bundle Size
- Core: 2kb gzipped
- With common plugins: ~4kb

### Documentation
- Good API docs
- Plugin documentation
- TypeScript support

### Score Breakdown
| Category | Score | Notes |
|----------|-------|-------|
| Activity | 4 | Active but slower |
| Community | 4 | Large community |
| Dependencies | 5 | Zero dependencies |
| Security | 5 | No issues |
| Documentation | 4 | Good |
| Performance | 5 | Smallest bundle |
| **TOTAL** | **4.1** | |

---

## moment.js

### ThoughtWorks Radar Status
**HOLD** ring (explicitly deprecated by maintainers)

### Health Metrics
- **Last commit:** 8 months ago
- **Last release:** 2 years ago
- **Status:** Maintenance mode only
- **Open issues:** 200+ (not being addressed)

### Repository Stats
```
Stars: 47.9k
Forks: 7.2k
Contributors: 600+
Weekly downloads: 20M+ (legacy usage)
```

### Dependencies
- Direct: 0
- Transitive: 0

### Security
- Historical CVEs (patched)
- ReDoS vulnerabilities in past

### Bundle Size
- Full library: 72kb minified + 18kb locale
- NOT tree-shakeable
- Mutable API (performance concerns)

### Documentation
- Comprehensive but for legacy API
- Migration guides to alternatives

### Score Breakdown
| Category | Score | Notes |
|----------|-------|-------|
| Activity | 1 | Maintenance mode |
| Community | 4 | Large but declining |
| Dependencies | 5 | Zero |
| Security | 3 | Historical issues |
| Documentation | 4 | Complete |
| Performance | 2 | Large, not tree-shakeable |
| **TOTAL** | **2.8** | |

---

## Recommendation

**Use date-fns** for new projects:
- Modern, functional API
- Tree-shakeable (only import what you use)
- Zero dependencies
- Active maintenance
- Strong TypeScript support

**Consider dayjs** if:
- Migrating from moment.js (compatible API)
- Bundle size is critical
- Need simple date operations

**Avoid moment.js**:
- Maintainers themselves recommend alternatives
- On ThoughtWorks "Hold" ring
- Large bundle size
- Mutable API causes bugs
