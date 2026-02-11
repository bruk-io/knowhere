# Library Evaluation Criteria

This reference provides detailed criteria for evaluating libraries and technologies.

## ThoughtWorks Technology Radar

The [ThoughtWorks Technology Radar](https://www.thoughtworks.com/radar) is an authoritative industry guide for technology adoption decisions. Check if the library or its category appears on the radar.

### Radar Quadrants

1. **Techniques** - Ways of doing things (methodologies, approaches)
2. **Tools** - Software utilities and platforms
3. **Platforms** - Infrastructure and runtime environments
4. **Languages & Frameworks** - Programming languages and frameworks (most libraries fall here)

### Radar Rings

| Ring | Meaning | Recommendation |
|------|---------|----------------|
| **Adopt** | Proven, mature, ready for broad use | Strong recommendation to use |
| **Trial** | Worth pursuing, proven enough to use with manageable risk | Use on a project that can handle risk |
| **Assess** | Worth exploring, understand how it impacts your enterprise | Investigate and prototype |
| **Hold** | Proceed with caution, may have significant issues | Avoid for new projects |

### Checking the Radar

1. Visit https://www.thoughtworks.com/radar
2. Use the search to find the technology
3. Check which ring it's in and read the blip description
4. Review the history - has it moved rings?
5. Note the volume (radar edition) for recency

**If not on radar:** The technology may be too new, too niche, or not evaluated. This isn't necessarily negative - evaluate using other criteria below.

## Health Metrics

### Activity Indicators (Weight: High)

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Last commit | < 3 months | 3-12 months | > 12 months |
| Last release | < 6 months | 6-18 months | > 18 months |
| Open issues trend | Decreasing/stable | Slowly growing | Rapidly growing |
| PR response time | < 1 week | 1-4 weeks | > 1 month |

### Popularity Metrics (Weight: Medium)

| Metric | Consider | Notes |
|--------|----------|-------|
| GitHub stars | Context-dependent | Compare to alternatives |
| Weekly downloads | Trend matters more | Look for growth/stability |
| Dependent packages | More = more testing | Can also mean breaking changes hurt more |
| Stack Overflow tags | Active community | Good for debugging support |

### Maintenance Signals (Weight: High)

**Positive Signs:**
- Multiple active maintainers (bus factor > 1)
- Corporate backing or sponsorship
- Clear governance model
- Regular release cadence
- Responsive to security issues

**Warning Signs:**
- Single maintainer
- Long gaps between releases
- Many stale PRs/issues
- No response to security reports
- Maintainer burnout signals

## Community Health

### Documentation Quality

- [ ] README with clear getting started
- [ ] API documentation complete
- [ ] Examples/tutorials available
- [ ] Changelog maintained
- [ ] Migration guides for major versions
- [ ] TypeScript types (for JS libraries)

### Support Channels

- [ ] GitHub Discussions or Issues active
- [ ] Discord/Slack community
- [ ] Stack Overflow presence
- [ ] Official forum or mailing list

### Contribution Health

- [ ] Contributing guide exists
- [ ] Code of conduct
- [ ] Clear PR review process
- [ ] New contributors welcomed
- [ ] Diverse contributor base

## Dependency Analysis

### Direct Dependencies

- **Count** - Fewer is generally better
- **Quality** - Are dependencies themselves well-maintained?
- **Security** - Any known vulnerabilities?
- **Overlap** - Do dependencies duplicate functionality you have?

### Transitive Dependencies

Total packages in the dependency tree:

| Count | Risk Level | Notes |
|-------|------------|-------|
| < 10 | Low | Minimal surface area |
| 10-50 | Moderate | Manageable |
| 50-100 | Elevated | Review major deps |
| 100+ | High | Carefully evaluate |

### Dependency Concerns

1. **Supply chain risk** - Each dependency is a potential attack vector
2. **Version conflicts** - Multiple versions of same package
3. **Abandoned deps** - Transitive deps that are unmaintained
4. **License compatibility** - Transitive deps with incompatible licenses

## Security Evaluation

### Check These Resources

1. **npm audit** / **pip-audit** / **cargo audit** - Built-in security scanners
2. **Snyk** (https://snyk.io) - Database of vulnerabilities
3. **GitHub Security Advisories** - Check repo's Security tab
4. **National Vulnerability Database** (https://nvd.nist.gov)
5. **Socket.dev** - Supply chain security for npm

### Security Scorecard

- [ ] No critical/high CVEs unpatched > 30 days
- [ ] Security policy published (SECURITY.md)
- [ ] Signed releases or commits
- [ ] 2FA required for maintainers
- [ ] Provenance attestation (for npm)

## License Compatibility

### Permissive Licenses (Low Risk)
- MIT, Apache 2.0, BSD, ISC
- Generally safe for any use

### Copyleft Licenses (Medium Risk)
- GPL, LGPL, AGPL, MPL
- May require source disclosure
- Check your organization's policy

### Red Flags
- No license specified
- Multiple conflicting licenses
- License recently changed
- Custom/non-OSI license

## Performance Considerations

### Bundle Size (Frontend)

Check https://bundlephobia.com for JavaScript packages:
- **Minified size** - Raw JavaScript size
- **Gzipped size** - What users download
- **Tree-shakeable** - Can unused code be removed?
- **Side effects** - Does it have side effects?

### Memory/CPU Overhead

- Review benchmarks if available
- Check for memory leak issues in GitHub
- Look for performance-related issues

## Scoring Framework

Use this framework to score libraries systematically:

```
Category               Weight   Score (1-5)   Weighted
─────────────────────────────────────────────────────
Activity & Maintenance   25%      ___         ___
Community & Support      20%      ___         ___
Dependencies             20%      ___         ___
Security                 15%      ___         ___
Documentation            10%      ___         ___
Performance              10%      ___         ___
─────────────────────────────────────────────────────
TOTAL                   100%                  ___/5.0
```

### Score Interpretation

| Score | Recommendation |
|-------|----------------|
| 4.5+ | Excellent choice, low risk |
| 3.5-4.4 | Good choice, acceptable risk |
| 2.5-3.4 | Proceed with caution |
| < 2.5 | Consider alternatives |

## Comparison Checklist

When comparing multiple libraries for the same purpose:

1. **Functional fit** - Does it solve your specific problem?
2. **API ergonomics** - Is it pleasant to use?
3. **Learning curve** - How long to become productive?
4. **Migration path** - Can you switch later if needed?
5. **Team familiarity** - Does anyone know it already?
6. **Ecosystem fit** - Works with your existing stack?

## Red Flags Summary

Stop and reconsider if you see:

- No releases in 18+ months
- Single maintainer who's gone quiet
- Many critical issues without response
- Security vulnerabilities unaddressed
- Hostile or toxic community
- Unclear or restrictive license
- Massive dependency tree (200+ packages)
- On ThoughtWorks Radar "Hold" ring

## Alternative Discovery

Tools to find alternatives:

- **npm:** https://npmtrends.com, https://npm-compare.com
- **Python:** https://libraries.io/pypi
- **General:** https://alternativeto.net
- **Awesome lists:** Search "awesome-{topic}" on GitHub

Always evaluate 2-3 alternatives before committing to a library.
