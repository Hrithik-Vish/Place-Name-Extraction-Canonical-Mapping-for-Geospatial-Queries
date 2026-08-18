import { useEffect, useMemo, useState } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap,
} from 'react-leaflet';
import {
  LocateFixed,
  MapPin,
  Maximize2,
} from 'lucide-react';

import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

/* =========================
   DEFAULT LEAFLET ICON
========================= */

delete L.Icon.Default.prototype._getIconUrl;

L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

/* =========================
   EXTRACTED PLACE ICON
========================= */

const extractedPlaceIcon = L.divIcon({
  className: 'geomapai-marker-wrapper',

  html: `
    <div class="geomapai-marker-pin">
      <div class="geomapai-marker-dot"></div>
    </div>
  `,

  iconSize: [32, 42],
  iconAnchor: [16, 42],
  popupAnchor: [0, -38],
});

/* =========================
   CURRENT LOCATION ICON
========================= */

const currentLocationIcon = L.divIcon({
  className: 'current-location-marker',

  html: `
    <div class="current-location-pulse">
      <div class="current-location-dot"></div>
    </div>
  `,

  iconSize: [34, 34],
  iconAnchor: [17, 17],
});

/* =========================
   SELECTED PLACE RECENTER
========================= */

const MapRecenter = ({ place }) => {
  const map = useMap();

  useEffect(() => {
    if (
      place &&
      place.status === 'resolved' &&
      typeof place.lat === 'number' &&
      typeof place.long === 'number'
    ) {
      map.flyTo(
        [place.lat, place.long],
        11,
        {
          duration: 1.2,
          easeLinearity: 0.25,
        }
      );
    }
  }, [place, map]);

  return null;
};

/* =========================
   FIT ALL LOCATIONS
========================= */

const MapFitController = ({
  trigger,
  places,
}) => {
  const map = useMap();

  useEffect(() => {
    if (!trigger || !places.length) {
      return;
    }

    const bounds = L.latLngBounds(
      places.map((place) => [
        place.lat,
        place.long,
      ])
    );

    if (!bounds.isValid()) {
      return;
    }

    map.flyToBounds(bounds, {
      paddingTopLeft: [50, 60],
      paddingBottomRight: [50, 60],
      duration: 1.3,
      maxZoom: 10,
    });
  }, [trigger, places, map]);

  return null;
};

/* =========================
   CURRENT LOCATION RECENTER
========================= */

const LocationController = ({
  currentLocation,
}) => {
  const map = useMap();

  useEffect(() => {
    if (
      currentLocation &&
      typeof currentLocation.lat === 'number' &&
      typeof currentLocation.lng === 'number'
    ) {
      map.flyTo(
        [
          currentLocation.lat,
          currentLocation.lng,
        ],
        13,
        {
          duration: 1.2,
          easeLinearity: 0.25,
        }
      );
    }
  }, [currentLocation, map]);

  return null;
};

/* =========================
   MAP VIEW
========================= */

const MapView = ({
  places = [],
  selectedPlace = null,
  fullScreen = false,
}) => {
  const [currentLocation, setCurrentLocation] =
    useState(null);

  const [locationStatus, setLocationStatus] =
    useState('idle');

  const [fitTrigger, setFitTrigger] =
    useState(0);

  const defaultCenter = [
    20.5937,
    78.9629,
  ];

  const resolvedPlaces = useMemo(
    () =>
      places.filter(
        (place) =>
          place.status === 'resolved' &&
          typeof place.lat === 'number' &&
          typeof place.long === 'number'
      ),
    [places]
  );

  const getSourceLabel = (source) => {
    if (source === 'local_geonames') {
      return 'Local GeoNames';
    }

    if (source === 'nominatim_fallback') {
      return 'Nominatim Fallback';
    }

    return 'Unavailable';
  };

  /* =========================
     YOUR LOCATION
  ========================= */

  const handleLocateMe = () => {
    if (!navigator.geolocation) {
      setLocationStatus('unsupported');
      return;
    }

    setLocationStatus('loading');

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCurrentLocation({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy: position.coords.accuracy,
        });

        setLocationStatus('success');
      },
      (error) => {
        console.error(
          'Geolocation error:',
          error
        );

        setLocationStatus('error');
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000,
      }
    );
  };

  /* =========================
     FIT ALL
  ========================= */

  const handleFitAll = () => {
    if (!resolvedPlaces.length) {
      return;
    }

    setFitTrigger(
      (previous) => previous + 1
    );
  };

  return (
    <div
      className={`map-wrapper ${
        fullScreen
          ? 'map-fullscreen'
          : ''
      }`}
    >
      <MapContainer
        center={defaultCenter}
        zoom={fullScreen ? 5 : 4}
        scrollWheelZoom={true}
        className="leaflet-map"
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
        />

        <MapRecenter
          place={selectedPlace}
        />

        <LocationController
          currentLocation={currentLocation}
        />

        <MapFitController
          trigger={fitTrigger}
          places={resolvedPlaces}
        />

        {/* =========================
            EXTRACTED LOCATIONS
        ========================= */}

        {resolvedPlaces.map(
          (place, index) => (
            <Marker
              key={`${place.raw}-${index}`}
              position={[
                place.lat,
                place.long,
              ]}
              icon={extractedPlaceIcon}
            >
              <Popup>
                <div className="map-popup">
                  <div className="popup-badge">
                    Resolved Location
                  </div>

                  <h3>
                    {place.canonical ||
                      'Unknown Location'}
                  </h3>

                  <p className="popup-original">
                    Input name:{' '}
                    {place.raw ||
                      'Not available'}
                  </p>

                  <div className="popup-divider" />

                  <div className="popup-info">
                    <span>
                      Confidence
                    </span>

                    <strong>
                      {Math.round(
                        (place.confidence || 0) *
                          100
                      )}
                      %
                    </strong>
                  </div>

                  <div className="popup-info">
                    <span>Source</span>

                    <strong>
                      {getSourceLabel(
                        place.source
                      )}
                    </strong>
                  </div>

                  <div className="popup-info">
                    <span>Latitude</span>

                    <strong>
                      {place.lat.toFixed(6)}
                    </strong>
                  </div>

                  <div className="popup-info">
                    <span>Longitude</span>

                    <strong>
                      {place.long.toFixed(6)}
                    </strong>
                  </div>

                  <div className="popup-divider" />

                  <p className="popup-reason">
                    {place.reason ||
                      'No explanation available.'}
                  </p>
                </div>
              </Popup>
            </Marker>
          )
        )}

        {/* =========================
            CURRENT LOCATION
        ========================= */}

        {currentLocation && (
          <Marker
            position={[
              currentLocation.lat,
              currentLocation.lng,
            ]}
            icon={currentLocationIcon}
            zIndexOffset={1000}
          >
            <Popup>
              <div className="map-popup">
                <div className="popup-badge current-location-badge">
                  Your Location
                </div>

                <h3>
                  Current Position
                </h3>

                <p className="popup-original">
                  Detected from your browser
                  location.
                </p>

                <div className="popup-divider" />

                <div className="popup-info">
                  <span>Latitude</span>

                  <strong>
                    {currentLocation.lat.toFixed(
                      6
                    )}
                  </strong>
                </div>

                <div className="popup-info">
                  <span>Longitude</span>

                  <strong>
                    {currentLocation.lng.toFixed(
                      6
                    )}
                  </strong>
                </div>

                <div className="popup-info">
                  <span>Accuracy</span>

                  <strong>
                    ±
                    {Math.round(
                      currentLocation.accuracy
                    )}
                    m
                  </strong>
                </div>
              </div>
            </Popup>
          </Marker>
        )}
      </MapContainer>

      {/* =========================
          MAP ACTIONS
      ========================= */}

      <div className="map-action-stack">
        <button
          type="button"
          className={`map-action-button ${
            locationStatus === 'loading'
              ? 'loading'
              : ''
          }`}
          onClick={handleLocateMe}
          disabled={
            locationStatus === 'loading'
          }
          title="Show your current location"
        >
          <LocateFixed size={16} />

          <span>
            {locationStatus === 'loading'
              ? 'Locating...'
              : 'Your Location'}
          </span>
        </button>

        <button
          type="button"
          className="map-action-button"
          onClick={handleFitAll}
          disabled={
            resolvedPlaces.length === 0
          }
          title="Fit all mapped locations"
        >
          <Maximize2 size={16} />

          <span>
            Fit All Locations
          </span>
        </button>
      </div>

      {/* =========================
          LOCATION MESSAGES
      ========================= */}

      {locationStatus === 'error' && (
        <div className="location-message error">
          <MapPin size={15} />

          <span>
            Unable to access your
            location. Please allow
            location permission.
          </span>
        </div>
      )}

      {locationStatus ===
        'unsupported' && (
        <div className="location-message error">
          <MapPin size={15} />

          <span>
            Geolocation is not supported
            by your browser.
          </span>
        </div>
      )}

      {locationStatus === 'success' && (
        <div className="location-message success">
          <MapPin size={15} />

          <span>
            Your current location is
            shown on the map.
          </span>
        </div>
      )}

      {/* =========================
          MAP COUNTER
      ========================= */}

      {resolvedPlaces.length > 0 && (
        <div className="map-counter">
          <span className="map-counter-dot" />

          {resolvedPlaces.length}{' '}
          {resolvedPlaces.length === 1
            ? 'location'
            : 'locations'}{' '}
          mapped
        </div>
      )}
    </div>
  );
};

export default MapView;