# Phase 0 Foundation

## Purpose

This document captures the planning outputs required to complete Phase 0:

- the problem statement
- the initial product boundary
- the first release boundary
- the success criteria
- the architectural source-of-truth decision

## Problem Statement

OpenAPI is effective for describing request and response contracts, but it does
not fully express the persistence model details required to generate ORM code in
a practical and repeatable way.

Examples of missing or underspecified persistence semantics include:

- relation ownership
- join table structure
- indexes and multi-column uniqueness
- database-only fields
- generated and audit columns
- the separation between DTOs and persistence entities

OpenModels exists to make those persistence semantics expressible without
abandoning OpenAPI as the main source document.

## Success Criteria

Phase 0 is successful when OpenModels has a clear and stable problem definition.
The primary success criterion is:

- OpenModels can express the required model information on top of OpenAPI.

For Phase 0, this means the format and architecture must support describing:

- entities and fields
- persistence-only fields
- relations and ownership
- indexes and uniqueness
- the separation between API schemas and persistence entities

## First Release Boundary

The first release is considered successful when:

- OpenModels can generate Drizzle model definition code and write it to files.

This first release boundary implies the minimum product surface is:

- parse an OpenAPI 3.1 document
- read and validate top-level `x-openmodels`
- normalize the source document into a canonical IR
- generate Drizzle schema definitions from that IR
- write generated output files to disk

## In Scope for the First Release

- OpenAPI 3.1 as the source document format
- top-level `x-openmodels` metadata
- entity, field, relation, and index definitions
- validation for unsupported or ambiguous persistence mappings
- normalization to a backend-agnostic IR
- Drizzle code generation
- file output for generated Drizzle schema files

## Out of Scope for the First Release

- a custom DSL separate from OpenAPI
- multiple ORM backends at launch
- migration generation
- DTO mapper generation
- full CLI polish beyond what is needed to prove file output
- deep support for every ORM-specific edge case

## Core Use Cases

### Use Case 1: API schema plus persistence metadata in one file

A developer writes a valid OpenAPI 3.1 document and adds `x-openmodels` at the
top level to define persistence behavior without splitting into a second schema
language.

### Use Case 2: DTO and entity separation

A developer defines `Create`, `Update`, and `Response` schemas in OpenAPI while
mapping them to a single persistence entity that includes generated and
database-only fields.

### Use Case 3: Relation-aware model generation

A developer expresses relation ownership and foreign key details explicitly so
the system can generate valid Drizzle relations instead of relying on unsafe
inference.

### Use Case 4: Drizzle file output

A developer runs OpenModels against an OpenAPI document and receives generated
Drizzle model definition files on disk.

## Architecture Decision Record

### ADR-0001: OpenAPI plus top-level x-openmodels is the source of truth

#### Status

Accepted

#### Decision

The canonical source document for OpenModels v0.1 is:

- an OpenAPI 3.1 document
- with persistence metadata stored under top-level `x-openmodels`

OpenModels will not introduce a separate DSL in the first release.

#### Rationale

- keeps API contract and persistence metadata colocated
- preserves compatibility with existing OpenAPI tooling
- reduces language and tooling surface area in the first release
- lets the project focus on semantics and normalization instead of syntax design

#### Consequences

- the implementation must resolve OpenAPI paths and OpenModels metadata together
- DTOs and entities must be modeled as related but separate concepts
- a canonical IR is required before generation
- unsupported cases must produce diagnostics instead of hidden guesses

## Exit Criteria for Phase 0

Phase 0 can be closed when:

- the success criteria are documented
- the first release boundary is documented
- the source-of-truth decision is documented
- follow-up work can proceed into schema, normalization, and Drizzle generation
