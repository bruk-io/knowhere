# License Configuration

Configure allowed licenses for your organization by setting the `ALLOWED_LICENSES` environment variable or passing them to the `check-license.sh` script.

## Default Allowed Licenses

By default, these permissive licenses are allowed:
- MIT
- Apache-2.0
- BSD-2-Clause
- BSD-3-Clause
- ISC
- 0BSD
- Unlicense
- CC0-1.0
- WTFPL

## Preset Configurations

### Permissive Only (Most Restrictive)
```bash
export ALLOWED_LICENSES="MIT,Apache-2.0,BSD-2-Clause,BSD-3-Clause,ISC,0BSD"
```

### Permissive + Weak Copyleft
```bash
export ALLOWED_LICENSES="MIT,Apache-2.0,BSD-2-Clause,BSD-3-Clause,ISC,MPL-2.0,LGPL-2.1,LGPL-3.0"
```

### GPL-Compatible (For GPL Projects)
```bash
export ALLOWED_LICENSES="MIT,Apache-2.0,BSD-2-Clause,BSD-3-Clause,ISC,GPL-2.0,GPL-3.0,LGPL-2.1,LGPL-3.0,AGPL-3.0"
```

### Enterprise Strict
```bash
export ALLOWED_LICENSES="MIT,Apache-2.0,BSD-3-Clause"
```

## Usage

### Command Line
```bash
# Use defaults
./check-license.sh npm lodash

# Specify allowed licenses
./check-license.sh npm lodash "MIT,Apache-2.0,BSD-3-Clause"

# Check multiple packages
for pkg in lodash express react; do
  ./check-license.sh npm "$pkg" "$ALLOWED_LICENSES"
done
```

### In Your Project

Create a `.lib-eval-config` file in your project root:
```
ALLOWED_LICENSES=MIT,Apache-2.0,BSD-3-Clause,ISC
```

Or add to your shell profile:
```bash
export ALLOWED_LICENSES="MIT,Apache-2.0,BSD-3-Clause,ISC"
```

## License Risk Levels

| Risk | Licenses | Notes |
|------|----------|-------|
| **Low** | MIT, ISC, BSD-*, Apache-2.0, 0BSD, Unlicense, CC0 | Safe for most uses |
| **Medium** | MPL-2.0, LGPL-* | File-level copyleft, usually OK for dynamic linking |
| **High** | GPL-2.0, GPL-3.0 | Strong copyleft, may require source disclosure |
| **Very High** | AGPL-* | Network copyleft, triggers on server use |
| **Unknown** | Custom, No License | Must review carefully, legal consultation recommended |

## License Compatibility Matrix

| Your License | Can Use |
|--------------|---------|
| MIT | MIT, BSD, ISC, Apache-2.0, 0BSD, Unlicense |
| Apache-2.0 | MIT, BSD, ISC, Apache-2.0 (NOT GPLv2-only) |
| GPL-3.0 | MIT, BSD, ISC, Apache-2.0, LGPL-3.0, GPL-3.0 |
| LGPL-3.0 | MIT, BSD, ISC, Apache-2.0, LGPL-3.0 |
| Proprietary | MIT, BSD, ISC, Apache-2.0 (check attribution requirements) |

## Common Issues

### "UNKNOWN" License
Package has no license specified. This legally means "all rights reserved."
- Do not use without explicit permission
- Contact maintainer to request license clarification
- Consider alternatives

### GPL in Proprietary Project
- You cannot statically link GPL code into proprietary software
- LGPL allows dynamic linking
- Consider MIT/BSD alternatives

### Apache-2.0 with GPLv2
- Apache-2.0 is incompatible with GPLv2 (but compatible with GPLv3)
- If your project is GPLv2-only, avoid Apache-2.0 dependencies

### Multi-License Packages
Some packages offer multiple licenses (e.g., "MIT OR Apache-2.0").
- You can choose which license to comply with
- Pick the one that's in your allowed list

## SPDX License IDs

Use SPDX identifiers for consistency:
- https://spdx.org/licenses/

Common mappings:
- "MIT License" -> MIT
- "Apache License 2.0" -> Apache-2.0
- "BSD 3-Clause" -> BSD-3-Clause
- "GNU General Public License v3.0" -> GPL-3.0
