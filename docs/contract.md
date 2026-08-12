# API Contract — PS-09 Place-Name Extraction & Canonical Mapping

## 1. Purpose

This document is the single source of truth for how the frontend and backend talk to each other. It defines the exact shape of the request sent to the backend, and the exact shape of every response the backend can send back — including error and edge cases.

**Hard rule:** No one changes a field name, field type, or response structure without updating this document first and telling the rest of the team. If your code and this document disagree, this document wins — fix your code, don't just work around it silently. Silent mismatches here are what break integration on the last day.

This contract applies to:
- Backend team (User, Member 3) — must produce exactly this
- Frontend team (Member 1, Member 2) — must consume exactly this
- Member 4 — error handling task must match the edge case shapes defined here

---

## 2. Endpoint Definition

- **Method:** `POST`
- **Path:** `/resolve`
- **Base URL:** stored as an environment variable on the frontend (e.g. `VITE_API_BASE_URL` or `.env` equivalent), never hardcoded. During local development this will point to `http://localhost:8000`; it will be updated once the backend is deployed/shared.
- **Content-Type:** `application/json`

---

## 3. Request Shape

```json
{
  "text": "Flood reported near Thane, spreading toward Kalyan. Springfield authorities also on alert."
}
```

| Field  | Type   | Required | Constraints                                                       |
|--------|--------|----------|---------------------------------------------------------------------|
| `text` | string | yes      | Must not be empty or whitespace-only. Frontend enforces this — see Section 5. |

The backend does not need to re-validate for empty/whitespace text, since the frontend guarantees this never reaches it. The backend should still not crash if it somehow receives an empty string (defensive coding), but this is not treated as a "normal" case to design around.

---

## 4. Response Shape — Success Case

```json
{
  "original_text": "Flood reported near Thane, spreading toward Kalyan. Springfield authorities also on alert.",
  "extracted": [
    {
      "raw": "Thane",
      "canonical": "Thane",
      "lat": 19.2183,
      "long": 72.9781,
      "confidence": 0.94,
      "reason": "Exact match in local gazetteer; high population; consistent with Maharashtra region context from co-occurring names.",
      "source": "local_geonames",
      "status": "resolved"
    },
    {
      "raw": "Kalyan",
      "canonical": "Kalyan",
      "lat": 19.2437,
      "long": 73.1355,
      "confidence": 0.91,
      "reason": "Exact match in local gazetteer; close proximity to other resolved place (Thane) in same text.",
      "source": "local_geonames",
      "status": "resolved"
    },
    {
      "raw": "Springfield",
      "canonical": null,
      "lat": null,
      "long": null,
      "confidence": 0.0,
      "reason": "Nominatim fallback request timed out; no local gazetteer match found.",
      "source": null,
      "status": "failed"
    }
  ],
  "message": null
}
```

### Top-level fields

| Field           | Type          | Meaning                                                              |
|-----------------|---------------|------------------------------------------------------------------------|
| `original_text` | string        | Echo of the input text exactly as submitted. Useful for frontend display/highlighting. |
| `extracted`     | array         | One entry per place name found by spaCy. Can be empty — see Section 5. |
| `message`       | string \| null | Human-readable note for special states (e.g. "no locations found"). `null` in a normal successful case with results. |

### Fields inside each `extracted` item

| Field        | Type            | Meaning                                                                 |
|--------------|-----------------|--------------------------------------------------------------------------|
| `raw`        | string          | The exact text span spaCy pulled out (before cleanup/matching).         |
| `canonical`  | string \| null  | The resolved, standardized place name. `null` if resolution failed.     |
| `lat`        | float \| null   | Latitude of resolved location. `null` if resolution failed.             |
| `long`       | float \| null   | Longitude of resolved location. `null` if resolution failed.            |
| `confidence` | float (0.0–1.0) | Disambiguation confidence score. `0.0` if resolution failed.            |
| `reason`     | string          | Human-readable explanation of why this canonical name was chosen (or why it failed). Always present — this is the field the demo click-to-reveal interaction uses. |
| `source`     | string \| null  | Where the match came from: `"local_geonames"` or `"nominatim_fallback"`. `null` if resolution failed. |
| `status`     | string          | Either `"resolved"` or `"failed"`. Frontend uses this to decide whether to render a pin or a "couldn't resolve" indicator. |

**Confidence is always a float between 0.0 and 1.0** (not a 0–100 integer). Everyone building against this contract should assume this.

---

## 5. Response Shape — Edge Cases

### 5.1 Empty or whitespace-only text

**Handled entirely on the frontend. The backend is never called.**

Before sending any request, the frontend checks the text input after trimming whitespace. If it's empty, the submit action is blocked and an inline message is shown (e.g. "Please enter some text before submitting"). No network request is made. The backend does not need any special-case logic for this and will never receive this case in practice.

### 5.2 No place names found in valid text

The backend receives and processes the request normally, but spaCy returns zero location entities. In this case, the backend **short-circuits immediately after the extraction step** — it skips cleanup (rapidfuzz), candidate generation (GeoNames/Nominatim), and disambiguation entirely, since there is nothing to resolve.

```json
{
  "original_text": "The weather today is sunny with a light breeze.",
  "extracted": [],
  "message": "No locations found in the provided text."
}
```

HTTP status: `200`. This is not treated as an error — it's a valid, expected outcome. Frontend shows a clear "no locations detected" state instead of an empty map with no explanation.

### 5.3 Partial failure (e.g. one name fails to resolve, others succeed)

If any single place name fails to resolve — for example the local gazetteer has no match and the Nominatim fallback call times out or errors — **the overall request still succeeds**. That specific entry is marked with `"status": "failed"` and its `canonical`, `lat`, `long`, and `source` fields are `null`, with `confidence` set to `0.0` and `reason` explaining what went wrong. All other entries that did resolve successfully are returned normally in the same `extracted` array.

HTTP status: `200`. The request as a whole is never failed just because one name inside it couldn't be resolved. See the `"Springfield"` entry in the Section 4 example — that's this exact case in context.

**This applies to Member 4's error handling task directly** — the Nominatim fallback function and general error handling should aim to always produce a `"failed"` entry for the specific name, never let one bad lookup crash or fail the whole `/resolve` call.

---

## 6. Field Reference Table (complete, all fields across all cases)

| Field                        | Type              | Where            | Meaning                                                        |
|-------------------------------|-------------------|------------------|------------------------------------------------------------------|
| `text`                        | string            | Request          | Raw input text submitted by the user.                           |
| `original_text`                | string            | Response (top)   | Echo of the submitted text.                                     |
| `extracted`                    | array             | Response (top)   | List of resolved/failed place entries. Can be empty.            |
| `message`                       | string \| null    | Response (top)   | Note for special states; `null` when there's nothing special to say. |
| `extracted[].raw`              | string            | Response (item)  | Exact text span spaCy extracted.                                 |
| `extracted[].canonical`        | string \| null    | Response (item)  | Standardized resolved place name, or `null` if failed.          |
| `extracted[].lat`              | float \| null     | Response (item)  | Latitude, or `null` if failed.                                   |
| `extracted[].long`             | float \| null     | Response (item)  | Longitude, or `null` if failed.                                  |
| `extracted[].confidence`       | float (0.0–1.0)   | Response (item)  | Disambiguation confidence; `0.0` if failed.                     |
| `extracted[].reason`           | string            | Response (item)  | Explanation of resolution decision or failure. Always present.  |
| `extracted[].source`           | string \| null    | Response (item)  | `"local_geonames"`, `"nominatim_fallback"`, or `null` if failed. |
| `extracted[].status`           | string            | Response (item)  | `"resolved"` or `"failed"`.                                      |

---

## 7. Versioning

**Current version: v1** — first draft, agreed 9 Aug 2026.

If this contract changes at any point (new field, renamed field, changed type, new edge case behavior), bump this version note and message the team immediately. Do not silently change behavior on one side only.

