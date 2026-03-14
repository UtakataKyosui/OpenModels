# OpenModels vs Plain OpenAPI-First Workflows

## What plain OpenAPI handles well

OpenAPI is already good at:

- request and response shapes
- required vs optional API fields
- enum and scalar validation
- client and server stub generation

## Where plain OpenAPI breaks down

Plain OpenAPI does not model persistence cleanly enough for reliable ORM or
migration generation.

Missing or ambiguous areas include:

- relation ownership
- foreign key storage details
- join table intent
- indexes and unique constraints
- database-only or audit columns
- generated column ownership
- DTO to persistence separation

## What OpenModels adds

OpenModels keeps the OpenAPI file but adds:

- `x-openmodels.entities`
- backend-neutral canonical IR
- output target declarations
- adapter-specific escape hatches
- migration plans
- mapper diagnostics

## Why not generate everything directly from OpenAPI

Direct generation from plain OpenAPI usually forces one of two bad outcomes:

- lossy guessing
- framework-specific annotations leaking into API schemas

OpenModels avoids both by making persistence intent explicit without replacing
OpenAPI as the public contract.

## Practical Rule

Use plain OpenAPI when you only need API contracts.

Use OpenModels when you need:

- ORM model generation
- migration planning
- DTO mapper generation
- stable separation between transport and persistence
