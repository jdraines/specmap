"""Reusable spec markdown content for functional tests."""

AUTH_SPEC = """\
# Authentication

This document describes the authentication system.

## Token Storage

Tokens are stored securely in the session store. Each token has a TTL
of 24 hours and is refreshed on activity.

### Encryption

All tokens are encrypted at rest using AES-256-GCM.

## Session Management

Sessions track user activity and expire after inactivity.
"""

# Minor wording change in Token Storage — fuzzy match should succeed (>0.8 similarity)
AUTH_SPEC_MINOR_EDIT = """\
# Authentication

This document describes the authentication system.

## Token Storage

Tokens are stored safely in the session store. Each token has a TTL
of 24 hours and is automatically refreshed on user activity.

### Encryption

All tokens are encrypted at rest using AES-256-GCM.

## Session Management

Sessions track user activity and expire after inactivity.
"""

# New paragraph inserted before Token Storage — offsets shift but text is identical
AUTH_SPEC_SHIFTED = """\
# Authentication

This document describes the authentication system.

> **Note:** This section was recently updated to reflect new security requirements.

## Token Storage

Tokens are stored securely in the session store. Each token has a TTL
of 24 hours and is refreshed on activity.

### Encryption

All tokens are encrypted at rest using AES-256-GCM.

## Session Management

Sessions track user activity and expire after inactivity.
"""

# Token Storage section completely rewritten — relocation should fail
AUTH_SPEC_REWRITTEN = """\
# Authentication

This document describes the authentication system.

## Token Storage

The token management system uses a distributed cache with Redis backing.
Tokens are validated on every request and have configurable expiration
policies based on the security level of the operation.

### Encryption

All tokens are encrypted at rest using AES-256-GCM.

## Session Management

Sessions track user activity and expire after inactivity.
"""

# Original spec + new Rate Limiting section added at end
AUTH_SPEC_EXTRA_SECTION = """\
# Authentication

This document describes the authentication system.

## Token Storage

Tokens are stored securely in the session store. Each token has a TTL
of 24 hours and is refreshed on activity.

### Encryption

All tokens are encrypted at rest using AES-256-GCM.

## Session Management

Sessions track user activity and expire after inactivity.

## Rate Limiting

API endpoints are rate-limited to 100 requests per minute per user.
"""

API_SPEC = """\
# API Design

This document describes the REST API design.

## Endpoints

All endpoints follow RESTful conventions with JSON payloads.

### GET Routes

GET routes return resource representations.

### POST Routes

POST routes create new resources.

## Error Handling

Errors return standard HTTP status codes with JSON error bodies.
"""

DEEP_SPEC = """\
# Level 1

Top-level content.

## Level 2

Second-level content.

### Level 3

Third-level content.

#### Level 4

Fourth-level content.

##### Level 5

Fifth-level content with details.
"""

UNICODE_SPEC = """\
# Authentifizierung

Dieses Dokument beschreibt das Authentifizierungssystem.

## Token-Speicherung

Tokens werden sicher im Sitzungsspeicher gespeichert. Jedes Token hat eine TTL
von 24 Stunden und wird bei Aktivitat aktualisiert.

## Sitzungsverwaltung

Sitzungen verfolgen die Benutzeraktivitat und laufen nach Inaktivitat ab.
"""

EMPTY_SPEC = """\
This is a markdown document with no headings.

Just some plain text content without any structure.
"""
