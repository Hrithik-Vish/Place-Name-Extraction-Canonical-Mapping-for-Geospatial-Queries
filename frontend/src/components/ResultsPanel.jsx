import { useMemo, useState } from 'react';
import {
  Search,
  MapPin,
  CheckCircle2,
  Download,
  SlidersHorizontal,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  FileJson,
} from 'lucide-react';

const ResultsPanel = ({
  places = [],
  onPlaceSelect,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterState, setFilterState] = useState('All');
  const [expandedReason, setExpandedReason] = useState(null);

  const resolvedPlaces = places.filter(
    (place) =>
      place.status === 'resolved' &&
      typeof place.lat === 'number' &&
      typeof place.long === 'number'
  );

  const states = useMemo(() => {
    const uniqueStates = new Set();

    places.forEach((place) => {
      if (place.state) {
        uniqueStates.add(place.state);
      }
    });

    return ['All', ...uniqueStates];
  }, [places]);

  const filteredPlaces = useMemo(() => {
    const search = searchTerm.toLowerCase().trim();

    return places.filter((place) => {
      const raw = place.raw?.toLowerCase() || '';
      const canonical =
        place.canonical?.toLowerCase() || '';
      const state =
        place.state?.toLowerCase() || '';

      const matchesSearch =
        raw.includes(search) ||
        canonical.includes(search) ||
        state.includes(search);

      const matchesState =
        filterState === 'All' ||
        place.state === filterState;

      return matchesSearch && matchesState;
    });
  }, [places, searchTerm, filterState]);

  const confidencePercent = (value) => {
    if (
      typeof value !== 'number' ||
      Number.isNaN(value)
    ) {
      return 0;
    }

    return Math.round(
      Math.max(0, Math.min(1, value)) * 100
    );
  };

  const getSourceLabel = (source) => {
    if (source === 'local_geonames') {
      return 'Local GeoNames';
    }

    if (source === 'nominatim_fallback') {
      return 'Nominatim Fallback';
    }

    return 'Unavailable';
  };

  const toggleReason = (key) => {
    setExpandedReason((current) =>
      current === key ? null : key
    );
  };

  /* =========================
     CSV EXPORT
  ========================= */

  const handleExportCSV = () => {
    if (!filteredPlaces.length) {
      alert('No results available to export.');
      return;
    }

    const headers = [
      'Historical Name',
      'Canonical Name',
      'Latitude',
      'Longitude',
      'Confidence',
      'Reason',
      'Source',
      'Status',
    ];

    const escapeCSV = (value) =>
      `"${String(value ?? '').replace(/"/g, '""')}"`;

    const rows = filteredPlaces.map((place) => [
      escapeCSV(place.raw),
      escapeCSV(place.canonical),
      place.lat ?? '',
      place.long ?? '',
      `${confidencePercent(place.confidence)}%`,
      escapeCSV(place.reason),
      escapeCSV(getSourceLabel(place.source)),
      escapeCSV(place.status),
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map((row) => row.join(',')),
    ].join('\n');

    const blob = new Blob([csvContent], {
      type: 'text/csv;charset=utf-8;',
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download =
      'geomapai_extracted_places.csv';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
  };

  /* =========================
     GEOJSON EXPORT
  ========================= */

  const handleExportGeoJSON = () => {
    if (!resolvedPlaces.length) {
      alert(
        'No resolved locations available to export.'
      );
      return;
    }

    const geojson = {
      type: 'FeatureCollection',

      features: resolvedPlaces.map(
        (place, index) => ({
          type: 'Feature',

          id: place.id ?? index + 1,

          geometry: {
            type: 'Point',

            // GeoJSON uses [longitude, latitude]
            coordinates: [
              place.long,
              place.lat,
            ],
          },

          properties: {
            historical_name:
              place.raw ?? '',
            canonical_name:
              place.canonical ?? '',
            confidence:
              place.confidence ?? 0,
            confidence_percent:
              confidencePercent(
                place.confidence
              ),
            reason:
              place.reason ?? '',
            source:
              place.source ?? null,
            status:
              place.status ?? 'resolved',
            state:
              place.state ?? null,
          },
        })
      ),
    };

    const blob = new Blob(
      [JSON.stringify(geojson, null, 2)],
      {
        type: 'application/geo+json;charset=utf-8;',
      }
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download =
      'geomapai_extracted_places.geojson';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
  };

  return (
    <div className="panel-card results-panel">
      <div className="results-header">
        <div className="panel-heading">
          <div className="panel-heading-icon green">
            <CheckCircle2 size={19} />
          </div>

          <div>
            <h2>Extraction Results</h2>

            <p>
              {places.length} location
              {places.length !== 1
                ? 's'
                : ''}{' '}
              detected
            </p>
          </div>
        </div>

        <div className="export-actions">
          <button
            className="export-button"
            onClick={handleExportCSV}
            disabled={!filteredPlaces.length}
          >
            <Download size={15} />
            Export CSV
          </button>

          <button
            className="export-button geojson-button"
            onClick={handleExportGeoJSON}
            disabled={!resolvedPlaces.length}
          >
            <FileJson size={15} />
            Export GeoJSON
          </button>
        </div>
      </div>

      <div className="results-toolbar">
        <div className="search-box">
          <Search size={17} />

          <input
            type="text"
            placeholder="Search places or states..."
            value={searchTerm}
            onChange={(event) =>
              setSearchTerm(event.target.value)
            }
          />
        </div>

        <div className="filter-box">
          <SlidersHorizontal size={16} />

          <select
            value={filterState}
            onChange={(event) =>
              setFilterState(event.target.value)
            }
          >
            {states.map((state) => (
              <option
                key={state}
                value={state}
              >
                {state === 'All'
                  ? 'All States'
                  : state}
              </option>
            ))}
          </select>
        </div>
      </div>

      {places.length > 0 && (
        <div className="results-summary">
          <span className="summary-resolved">
            <CheckCircle2 size={12} />
            {resolvedPlaces.length} resolved
          </span>

          <span className="summary-failed">
            {places.length -
              resolvedPlaces.length}{' '}
            unresolved
          </span>
        </div>
      )}

      <div className="results-count">
        Showing {filteredPlaces.length} of{' '}
        {places.length} results
      </div>

      <div className="table-container">
        <table className="results-table">
          <thead>
            <tr>
              <th>Historical Name</th>
              <th>Canonical Name</th>
              <th>Location</th>
              <th>Confidence</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>

          <tbody>
            {filteredPlaces.length === 0 ? (
              <tr>
                <td colSpan="6">
                  <div className="empty-results">
                    <div className="empty-results-icon">
                      <Search size={24} />
                    </div>

                    <h3>
                      {places.length === 0
                        ? 'No locations detected'
                        : 'No matching results'}
                    </h3>

                    <p>
                      {places.length === 0
                        ? 'Run text analysis to see detected places here.'
                        : 'Try changing your search or filter.'}
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              filteredPlaces.map(
                (place, index) => {
                  const key = `${place.raw}-${index}`;

                  const isResolved =
                    place.status ===
                    'resolved';

                  const confidence =
                    confidencePercent(
                      place.confidence
                    );

                  const isOpen =
                    expandedReason === key;

                  return (
                    <FragmentRow
                      key={key}
                      place={place}
                      isResolved={isResolved}
                      confidence={confidence}
                      isOpen={isOpen}
                      getSourceLabel={
                        getSourceLabel
                      }
                      toggleReason={
                        toggleReason
                      }
                      onPlaceSelect={
                        onPlaceSelect
                      }
                      rowKey={key}
                    />
                  );
                }
              )
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const FragmentRow = ({
  place,
  isResolved,
  confidence,
  isOpen,
  getSourceLabel,
  toggleReason,
  onPlaceSelect,
  rowKey,
}) => {
  return (
    <>
      <tr
        className={
          isOpen
            ? 'result-row-open'
            : ''
        }
      >
        <td>
          <div className="historical-name">
            <span>
              {place.raw || 'Unknown'}
            </span>
          </div>
        </td>

        <td>
          {isResolved ? (
            <div className="canonical-name">
              <CheckCircle2 size={16} />
              {place.canonical}
            </div>
          ) : (
            <div className="failed-name">
              Unresolved
            </div>
          )}
        </td>

        <td>
          {isResolved &&
          typeof place.lat ===
            'number' &&
          typeof place.long ===
            'number' ? (
            <div className="location-cell">
              {place.state && (
                <strong>
                  {place.state}
                </strong>
              )}

              <span>
                {place.lat.toFixed(4)},{' '}
                {place.long.toFixed(4)}
              </span>
            </div>
          ) : (
            <span className="not-available">
              Not available
            </span>
          )}
        </td>

       <td>
  <div className="confidence-cell">
    <div className="confidence-value-row">
      <span
        className={`confidence-badge ${
          confidence >= 90
            ? 'high'
            : confidence >= 60
            ? 'medium'
            : 'low'
        }`}
      >
        {confidence}%
      </span>
    </div>

    <div className="confidence-bar">
      <div
        className={`confidence-fill ${
          confidence >= 90
            ? 'high'
            : confidence >= 60
            ? 'medium'
            : 'low'
        }`}
        style={{
          '--confidence-width': `${confidence}%`,
        }}
      />
    </div>
  </div>
</td>

        <td>
          <span
            className={`status-badge ${
              isResolved
                ? 'resolved'
                : 'failed'
            }`}
          >
            {isResolved
              ? 'Resolved'
              : 'Failed'}
          </span>
        </td>

        <td>
          <div className="result-actions">
            <button
  className="reason-button"
  onClick={() =>
    toggleReason(rowKey)
  }
>
  {isOpen
    ? 'Hide reason'
    : isResolved
    ? 'Why was this location selected?'
    : "Why couldn't this location be resolved?"}

  {isOpen ? (
    <ChevronUp size={14} />
  ) : (
    <ChevronDown size={14} />
  )}
</button>

            {isResolved && (
              <button
                className="view-button"
                onClick={() =>
                  onPlaceSelect(place)
                }
              >
                <MapPin size={15} />
                View
              </button>
            )}
          </div>
        </td>
      </tr>

      {isOpen && (
        <tr className="reason-expanded-row">
          <td colSpan="6">
            <div className="reason-expanded-card">
              <div className="reason-expanded-icon">
                <ShieldCheck size={18} />
              </div>

              <div className="reason-expanded-content">
                <div className="reason-expanded-header">
                  <strong>
  {isResolved
    ? 'Why was this location selected?'
    : "Why couldn't this location be resolved?"}
</strong>

                  <span>
                    {place.raw} →{' '}
                    {isResolved
                      ? place.canonical
                      : 'Unresolved'}
                  </span>
                </div>

                <p>
                  {place.reason ||
                    'No explanation was provided.'}
                </p>

                <div className="reason-expanded-meta">
                  <span>
                    Source:{' '}
                    <strong>
                      {getSourceLabel(
                        place.source
                      )}
                    </strong>
                  </span>

                  <span>
                    Confidence:{' '}
                    <strong>
                      {confidence}%
                    </strong>
                  </span>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
};

export default ResultsPanel;