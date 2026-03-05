---
globs: ["**/deployment/**/*.likec4", "**/deployment/**/*.c4", "**/views/deployment/**/*.likec4", "**/views/deployment/**/*.c4"]
---

# C4 Deployment Model Rules

You are editing a deployment model or deployment view file. Deployment describes how instances of software systems and/or containers are deployed onto physical or cloud infrastructure in a given environment.

## Deployment Node Hierarchy
- Environment (production, staging, dev)
  - Region/Zone (us-east, eu-west)
    - Infrastructure (Kubernetes cluster, VM, serverless)
      - Instances of software systems and/or containers

## Key Rules
- Use `instanceOf` to deploy logical model containers to physical nodes
- Instances inherit properties from their source container
- Override title/technology on instances for environment-specific details
- Deployment-specific relationships (replication, failover) are defined here, not in the logical model
- Use `style { multiple true }` for horizontally scaled instances
- Create one deployment view per deployment environment (production, staging, development, etc.) — environments differ in topology, scale, and configuration; separate views prevent conflation

## What Belongs Here
- Physical topology: environments, regions, clusters, VMs
- How instances of software systems and/or containers are deployed (which systems/containers run where)
- Deployment-specific relationships (replication, failover, load balancing)

## Audience

Developers and infrastructure/operations staff. Deployment diagrams bridge the gap between people who build software and people who run it.

## Naming Consistency

Container names in the logical model must match the container names referenced in `instanceOf` declarations. A container called "API Server" in the logical model must appear as "API Server" in the deployment file — renaming it breaks the link between the logical and deployment views.

## What Does NOT Belong Here
- Logical architecture (that's the model)
- Business relationships between systems (that's context level)
- Component internals
