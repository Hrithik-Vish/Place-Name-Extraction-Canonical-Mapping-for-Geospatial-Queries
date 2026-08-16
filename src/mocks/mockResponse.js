// src/mocks/mockResponse.js
//
// Mock payloads matching the agreed PS-09 API Contract for POST /resolve.
// Used by App.jsx when USE_MOCK = true, so frontend work can proceed
// independently of backend availability.

/**
 * Successful resolution with a mix of resolved and failed extractions.
 * Demonstrates the "partial failure" case: not every extracted place
 * name is guaranteed to resolve to a canonical location.
 */
export const MOCK_SUCCESS_RESPONSE = {
  original_text:
    "We drove from Bengaluru through Hosur before stopping near Krishnagiri, then lost the trail somewhere past Zzyzxville on the old map.",
  message: null,
  extracted: [
    {
      raw: "Bengaluru",
      status: "resolved",
      canonical: "Bengaluru, Karnataka, India",
      lat: 12.9716,
      long: 77.5946,
      confidence: 0.97,
      reason: "Exact match on primary name in local GeoNames index.",
      source: "local_geonames",
    },
    {
      raw: "Krishnagiri",
      status: "resolved",
      canonical: "Krishnagiri, Tamil Nadu, India",
      lat: 12.5266,
      long: 78.2150,
      confidence: 0.89,
      reason:
        "High-confidence fuzzy match; raw alias 'Krishnagiri' matched against alternate names table with minor diacritic normalization.",
      source: "local_geonames",
    },
    {
      raw: "Zzyzxville",
      status: "failed",
      canonical: null,
      lat: null,
      long: null,
      confidence: 0.0,
      reason:
        "No candidate found in local GeoNames index; fallback lookup to Nominatim timed out after 5000ms.",
      source: "local_geonames",
    },
  ],
};

/**
 * Empty result: the text was valid and processed, but no place names
 * were detected in it at all. Distinct from a network/server error.
 */
export const MOCK_EMPTY_RESPONSE = {
  original_text: "I went for a walk and thought about nothing in particular.",
  extracted: [],
  message: "No locations found in the provided text.",
};
