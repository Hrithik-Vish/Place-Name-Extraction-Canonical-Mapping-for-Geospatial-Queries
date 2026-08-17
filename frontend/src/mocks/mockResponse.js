// src/mocks/mockResponse.js
//
// Fixture payloads matching contract.md v1 for POST /resolve.
// Used for offline frontend development when the backend isn't reachable —
// see USE_MOCK in App.jsx. Field shape here is the single source of truth
// from contract.md Section 4 & 6; if the backend ever disagrees with this
// shape, the contract wins — this file should be updated to match it, not
// the other way around.

/**
 * Success response with a mix of resolved and failed entries, mirroring
 * the exact example in contract.md Section 4 (Thane / Kalyan / Springfield).
 * Demonstrates the partial-failure case: one entry can fail to resolve
 * while the rest of the request still succeeds with HTTP 200.
 */
export const MOCK_SUCCESS_RESPONSE = {
  original_text:
    'Flood reported near Thane, spreading toward Kalyan. Springfield authorities also on alert.',
  extracted: [
    {
      raw: 'Thane',
      canonical: 'Thane',
      lat: 19.2183,
      long: 72.9781,
      confidence: 0.94,
      reason:
        'Exact match in local gazetteer; high population; consistent with Maharashtra region context from co-occurring names.',
      source: 'local_geonames',
      status: 'resolved',
    },
    {
      raw: 'Kalyan',
      canonical: 'Kalyan',
      lat: 19.2437,
      long: 73.1355,
      confidence: 0.91,
      reason:
        'Exact match in local gazetteer; close proximity to other resolved place (Thane) in same text.',
      source: 'local_geonames',
      status: 'resolved',
    },
    {
      // Deliberately non-Indian so it fails under the India-only Nominatim
      // scope (see docs/member4_tasks.md Task 8) — this is the documented,
      // expected failure mode, not a bug to "fix" if seen during testing.
      raw: 'Springfield',
      canonical: null,
      lat: null,
      long: null,
      confidence: 0.0,
      reason:
        'No local gazetteer match found; Nominatim fallback (India-scoped) also returned no results.',
      source: null,
      status: 'failed',
    },
  ],
  message: null,
};

/**
 * Edge case 5.2 — valid text, but spaCy extracted zero place names.
 * Backend short-circuits after extraction; extracted is [] and message
 * explains why. HTTP 200, not an error.
 */
export const MOCK_EMPTY_RESPONSE = {
  original_text: 'The weather today is sunny with a light breeze.',
  extracted: [],
  message: 'No locations found in the provided text.',
};
