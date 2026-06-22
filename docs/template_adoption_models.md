# Template Adoption Models

This document describes the main ways engineering teams can adopt an
AI-assisted development workflow template and the tradeoffs of each
approach.

## Overview

Template adoption differs mainly along three dimensions:

- where the files physically live
- where changes persist
- how much state is shared across repositories

These choices affect portability, governance, and day-to-day workflow.

## 1. Symlinked Assets

A symlinked setup points one repository at files that physically live
somewhere else.

### How It Works

- the consuming repo contains symlinks
- the real files live in a shared local path or another repository
- editing the target updates the shared source immediately

### Strengths

- one shared source of truth
- fast reuse across multiple local repos
- convenient for a single developer maintaining a personal workflow
  environment

### Weaknesses

- not portable across machines by default
- fragile in public or open-source contexts
- hidden coupling between repos
- poor fit for outside adopters or enterprise consumers

### Best Fit

- personal local workflow
- one developer maintaining shared config across many repos

## 2. Checked-In Files

A checked-in setup copies template files into the consuming repository
as real files tracked by that repository's Git history.

### How It Works

- files are copied into the project repo
- the consuming repo tracks them directly
- changes persist only in that repo unless intentionally promoted back

### Strengths

- portable
- visible and auditable in the project's history
- no hidden external dependency
- strong fit for existing repos adopting only part of a template

### Weaknesses

- drift can emerge between template and adopted copies
- improvements are not shared automatically
- promotion back to the template repo is manual

### Best Fit

- existing production repos
- enterprise teams adopting selected workflow structure
- public repos where portability matters

## 3. Clone the Template Repo

Cloning the template repo creates a local working copy of the template
repository itself.

### How It Works

- the repo is cloned directly
- work happens on the template repo, not inside another project repo
- this works when the template itself is the starting repository

### Strengths

- ideal when the whole template becomes the new repo base
- preserves the original structure and history
- simple for greenfield projects

### Weaknesses

- not the right model for integrating into an already-existing repo
- can blur template maintenance with template consumption

### Best Fit

- starting a brand-new repo from the template
- modifying the template itself as a standalone artifact

## 4. GitHub Template Repository

This is a hosted variation of the "clone as starting point" model.

### How It Works

- a user clicks "Use this template" on GitHub
- GitHub creates a new repository initialized from the template

### Strengths

- easy for outside adopters
- good for standardized repo bootstrapping
- avoids manual copy/paste

### Weaknesses

- better for full-repo adoption than partial adoption
- downstream repos still diverge unless update workflows are defined

### Best Fit

- greenfield project initialization
- standardized team repo creation

## 5. Scaffold or Generator Tooling

A script or generator copies selected template components into a target
repo.

### How It Works

- a CLI, script, or generator creates files and folders from template
  definitions
- teams adopt only the parts they need

### Strengths

- repeatable
- selective adoption
- good balance between portability and standardization

### Weaknesses

- requires maintenance of the generator itself
- updates still need a synchronization strategy

### Best Fit

- organizations with repeated setup needs
- templates with optional modules or variants

## 6. Git Submodule

A repo embeds another repo at a fixed commit.

### How It Works

- the consumer repo references the template repo as a submodule
- the template remains an external repo with pinned versioning

### Strengths

- explicit version linkage
- shared upstream source remains separate
- consumers can update intentionally

### Weaknesses

- many teams dislike submodule workflow complexity
- awkward for non-Git-heavy users
- not ideal for simple docs or instruction adoption

### Best Fit

- teams comfortable with Git internals
- strict versioned dependency on shared content

## 7. Git Subtree or Vendor Copy

The template repo is imported into the project while preserving an
upstream relationship more explicitly than ad hoc copying.

### How It Works

- shared content is copied into the repo through Git tooling
- upstream updates can be pulled again later

### Strengths

- checked-in local files
- more updateable than pure manual copy
- easier for many consumers than submodules

### Weaknesses

- more process overhead than plain copy
- still requires explicit sync discipline

### Best Fit

- teams that want local ownership plus occasional upstream syncing

## Which Adoption Methods Are Most Common In Production

For production engineering environments, the most common patterns are
usually:

- checked-in files copied into the consuming repo
- GitHub template repos for new project creation
- scaffold or generator tooling for standardized adoption
- sometimes subtree or vendor-copy workflows in more mature platform
  teams

Less common as a primary enterprise adoption model:

- symlinks
- submodules

Symlinks are usually too machine-local and fragile for broad team use.
Submodules are viable, but many teams avoid them because of workflow
complexity.

## Best Fit For This Template

For the kind of template this repository provides:

- existing repos should usually adopt by checking in relevant files
- new repos can be created directly from the template
- future mature adoption may use scaffolding or a promotion workflow

This means a consuming project can act as an instantiated copy of the
template, while this repository remains the canonical source pattern.

## Short Conclusion

Symlinks optimize for local shared state.

Checked-in files optimize for portability and project-local ownership.

Cloning or templating a repo optimizes for starting a new repository
from a standard base.

For most production teams adopting workflow structure into an existing
codebase, checked-in files are the most realistic default.
