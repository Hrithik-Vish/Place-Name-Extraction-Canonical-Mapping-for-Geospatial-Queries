import { useEffect, useMemo, useState } from 'react';
import {
  Map,
  MapPin,
  CheckCircle2,
  Database,
  AlertCircle,
} from 'lucide-react';

import Header from './components/Header';
import Sidebar from './components/Sidebar';
import TextHighlighter from './components/TextHighlighter';
import ResultsPanel from './components/ResultsPanel';
import MapView from './components/MapView';

import {
  MOCK_SUCCESS_RESPONSE,
  MOCK_EMPTY_RESPONSE,
} from './mocks/mockResponse';

import './App.css';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  'http://localhost:8000';

// Dev-only offline toggle. When true, /resolve is never actually called —
// a fixture matching contract.md is returned instead after a short
// simulated delay, so the full UI (including the loading animation) can
// be seen and tested without the backend running.
//
// Defaults to FALSE — this build talks to the real backend at
// API_BASE_URL (see the fetch call in the try block below). Set
// VITE_API_BASE_URL in .env (see .env.example) if the backend isn't on
// localhost:8000. Flip this back to true only for offline UI/animation
// development when no backend is running.
const USE_MOCK = false;
const MOCK_DELAY_MS = 2200;

// Text containing the whole word "empty" routes to the zero-results
// fixture instead of the success one, so both edge cases in contract.md
// Section 5 are reachable via USE_MOCK without touching this file again.
function resolveMock(text) {
  return new Promise((resolve) => {
    setTimeout(() => {
      const useEmpty = /\bempty\b/i.test(text);
      const base = useEmpty
        ? MOCK_EMPTY_RESPONSE
        : MOCK_SUCCESS_RESPONSE;

      resolve({ ...base, original_text: text });
    }, MOCK_DELAY_MS);
  });
}

function App() {
  const [theme, setTheme] = useState('light');

  const [extractedPlaces, setExtractedPlaces] =
    useState([]);

  const [responseMessage, setResponseMessage] =
    useState(null);

  const [isExtracting, setIsExtracting] =
    useState(false);

  const [apiError, setApiError] = useState('');

  const [selectedPlace, setSelectedPlace] =
    useState(null);

  const [activeTab, setActiveTab] =
    useState('Text Analysis');

  useEffect(() => {
    document.documentElement.setAttribute(
      'data-theme',
      theme
    );
  }, [theme]);

  const toggleTheme = () => {
    setTheme((previous) =>
      previous === 'light'
        ? 'dark'
        : 'light'
    );
  };

  const handleExtract = async (text) => {
    const trimmedText = text.trim();

    if (!trimmedText) {
      return;
    }

    setIsExtracting(true);
    setApiError('');
    setResponseMessage(null);
    setExtractedPlaces([]);
    setSelectedPlace(null);

    try {
      let data;

      if (USE_MOCK) {
        data = await resolveMock(trimmedText);
      } else {
        const response = await fetch(
          `${API_BASE_URL}/resolve`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              text: trimmedText,
            }),
          }
        );

        if (!response.ok) {
          let errorMessage =
            'Backend request failed.';

          try {
            const errorData =
              await response.json();

            if (
              errorData?.message &&
              typeof errorData.message === 'string'
            ) {
              errorMessage =
                errorData.message;
            } else if (
              typeof errorData?.detail === 'string'
            ) {
              // FastAPI's own HTTPException(detail="...") shape.
              errorMessage =
                errorData.detail;
            } else if (
              Array.isArray(errorData?.detail) &&
              errorData.detail.length > 0
            ) {
              // FastAPI/Pydantic's automatic request-validation shape —
              // detail is a list of {loc, msg, type} objects, not a
              // string. Surface the first message rather than stringify
              // the whole array (which renders as "[object Object]").
              const [firstIssue] = errorData.detail;

              errorMessage =
                firstIssue?.msg &&
                typeof firstIssue.msg === 'string'
                  ? firstIssue.msg
                  : errorMessage;
            }
          } catch {
            // Ignore invalid error JSON
          }

          throw new Error(errorMessage);
        }

        data = await response.json();
      }

      if (
        !data ||
        typeof data !== 'object'
      ) {
        throw new Error(
          'Invalid response received from backend.'
        );
      }

      if (!Array.isArray(data.extracted)) {
        throw new Error(
          'Backend response is missing the extracted array.'
        );
      }

      const normalizedPlaces =
        data.extracted.map((place) => ({
          raw: place.raw ?? '',
          canonical:
            place.canonical ?? null,
          lat:
            typeof place.lat === 'number'
              ? place.lat
              : null,
          long:
            typeof place.long === 'number'
              ? place.long
              : null,
          confidence:
            typeof place.confidence ===
              'number'
              ? place.confidence
              : 0,
          reason:
            place.reason ??
            'No explanation provided.',
          source:
            place.source ?? null,
          status:
            place.status === 'resolved'
              ? 'resolved'
              : 'failed',
          state:
            place.state ?? null,
        }));

      setExtractedPlaces(
        normalizedPlaces
      );

      setResponseMessage(
        data.message ?? null
      );
    } catch (error) {
      console.error(
        'Extraction error:',
        error
      );

      setExtractedPlaces([]);
      setResponseMessage(null);

      setApiError(
        error?.message ||
          'Unable to connect to the backend.'
      );
    } finally {
      setIsExtracting(false);
    }
  };

  const stats = useMemo(() => {
    const resolved =
      extractedPlaces.filter(
        (place) =>
          place.status === 'resolved'
      );

    const highConfidence =
      resolved.filter(
        (place) =>
          typeof place.confidence ===
            'number' &&
          place.confidence >= 0.9
      );

    const states = new Set();

    resolved.forEach((place) => {
      if (place.state) {
        states.add(place.state);
      }
    });

    // contract.md's extracted[] items don't currently include a `state`
    // field — every place normalized in handleExtract carries state: null
    // against the real backend today. hasStateData distinguishes "the
    // backend sent state, and this text genuinely resolved to zero
    // distinct states" (states.size === 0 but hasStateData is true) from
    // "the backend doesn't send state data at all" (nothing to count).
    // Only the first case should ever render as a real "0". See the
    // States Covered stat card below.
    const hasStateData = extractedPlaces.some(
      (place) => Boolean(place.state)
    );

    return {
      locations:
        extractedPlaces.length,
      highConfidence:
        highConfidence.length,
      states: states.size,
      hasStateData,
      resolved: resolved.length,
    };
  }, [extractedPlaces]);

  return (
    <div className="app-container">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      <div className="main-content">
        <Header
          theme={theme}
          toggleTheme={toggleTheme}
        />

        <main className="page-content">
          {activeTab === 'Text Analysis' && (
            <div className="dashboard-page">
              <div className="welcome-section">
                <span className="eyebrow">
                  <span className="eyebrow-dot" />
                  ANALYSIS WORKSPACE
                </span>

                <h2>
                  Transform historical text
                  into
                  <span>
                    {' '}
                    geospatial intelligence.
                  </span>
                </h2>

                <p>
                  Extract historical place
                  names, map them to modern
                  canonical locations, and
                  understand why each location
                  was selected.
                </p>
              </div>

              {apiError && (
                <div className="global-error">
                  <AlertCircle size={18} />

                  <div>
                    <strong>
                      Backend connection failed
                    </strong>

                    <p>{apiError}</p>
                  </div>
                </div>
              )}

              {responseMessage && (
                <div className="info-message">
                  <AlertCircle size={18} />

                  <span>
                    {responseMessage}
                  </span>
                </div>
              )}

              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-icon blue">
                    <MapPin size={20} />
                  </div>

                  <div>
                    <span>
                      Locations Detected
                    </span>

                    <strong>
                      {stats.locations}
                    </strong>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon green">
                    <CheckCircle2 size={20} />
                  </div>

                  <div>
                    <span>
                      High Confidence
                    </span>

                    <strong>
                      {stats.highConfidence}
                    </strong>
                  </div>
                </div>

                <div
                  className="stat-card"
                  title={
                    stats.hasStateData
                      ? undefined
                      : 'State data is not provided by the connected backend yet.'
                  }
                >
                  <div className="stat-icon purple">
                    <Map size={20} />
                  </div>

                  <div>
                    <span>
                      States Covered
                    </span>

                    <strong>
                      {stats.hasStateData
                        ? stats.states
                        : '—'}
                    </strong>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon orange">
                    <Database size={20} />
                  </div>

                  <div>
                    <span>
                      Processing Status
                    </span>

                    <strong className="online-text">
                      {isExtracting
                        ? 'Processing'
                        : 'Ready'}
                    </strong>
                  </div>
                </div>
              </div>

              <div className="dashboard-layout">
                <div className="analysis-column">
                  <TextHighlighter
                    onExtract={handleExtract}
                    isExtracting={
                      isExtracting
                    }
                  />
                </div>

                <div className="visual-column">
                  <div className="map-card">
                    <div className="map-card-header">
                      <div>
                        <h3>
                          Spatial Visualization
                        </h3>

                        <p>
                          Detected locations on
                          the map
                        </p>
                      </div>

                      <div className="map-live-status">
                        <span />
                        Live
                      </div>
                    </div>

                    <div className="map-card-body">
                      <MapView
                        places={
                          extractedPlaces
                        }
                        selectedPlace={
                          selectedPlace
                        }
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="results-full-width">
                <ResultsPanel
                  places={
                    extractedPlaces
                  }
                  onPlaceSelect={
                    setSelectedPlace
                  }
                />
              </div>
            </div>
          )}

          {activeTab === 'Map View' && (
            <div className="full-page">
              <div className="page-heading">
                <span className="eyebrow">
                  <span className="eyebrow-dot" />
                  SPATIAL EXPLORER
                </span>

                <h2>
                  Global Map View
                </h2>

                <p>
                  Explore all resolved
                  locations across
                  geographical space.
                </p>
              </div>

              <div className="full-map-card">
                <MapView
                  places={
                    extractedPlaces
                  }
                  selectedPlace={
                    selectedPlace
                  }
                  fullScreen
                />
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;