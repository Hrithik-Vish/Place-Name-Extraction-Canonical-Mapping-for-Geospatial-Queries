// src/components/SpatialLoader.jsx
import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MapPin } from "lucide-react";

const SCAN_PHRASES = [
  "Extracting entities...",
  "Fuzzy matching aliases...",
  "Resolving coordinates...",
];

const PHRASE_INTERVAL_MS = 1400;
const PIN_HOLD_MS = 800; // time to admire "Locations Mapped!" before exit
const RADAR_SIZE = 280;
const RADAR_CENTER = RADAR_SIZE / 2;

/**
 * Deterministic-looking "random" blip positions on the radar face.
 * Generated once per mount so blips don't jitter on re-render.
 */
function useRadarBlips(count = 6) {
  return useMemo(() => {
    return Array.from({ length: count }, (_, i) => {
      // Keep blips inside the radar face, away from the very edge.
      const angle = (i / count) * Math.PI * 2 + Math.random() * 0.6;
      const radius = 40 + Math.random() * 90;
      return {
        id: i,
        x: RADAR_CENTER + Math.cos(angle) * radius,
        y: RADAR_CENTER + Math.sin(angle) * radius,
        delay: 0.4 + Math.random() * 2.2,
      };
    });
  }, [count]);
}

/**
 * SpatialLoader
 *
 * Props:
 *  - isLoading: boolean     Drives Phase 1 (scanning). When it flips to
 *                            false, Phase 2 (pin drop) then Phase 3
 *                            (reveal/exit) play automatically.
 *  - onComplete: () => void Called once the exit animation finishes,
 *                            so the parent can swap in the resolved UI.
 */
export default function SpatialLoader({ isLoading, onComplete }) {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [pinDropped, setPinDropped] = useState(false);
  const [visible, setVisible] = useState(isLoading);

  const blips = useRadarBlips(6);

  // Keep the overlay mounted for the whole loading run, including the
  // brief window after isLoading flips false where Phases 2 & 3 play.
  useEffect(() => {
    if (isLoading) {
      setVisible(true);
      setPinDropped(false);
    }
  }, [isLoading]);

  // Cycle the scanning phrase while Phase 1 is active.
  useEffect(() => {
    if (!isLoading) return undefined;

    const id = setInterval(() => {
      setPhraseIndex((prev) => (prev + 1) % SCAN_PHRASES.length);
    }, PHRASE_INTERVAL_MS);

    return () => clearInterval(id);
  }, [isLoading]);

  // Phase 1 -> Phase 2: once loading finishes, trigger the pin drop.
  useEffect(() => {
    if (isLoading) return undefined;
    if (!visible) return undefined;

    const dropTimer = setTimeout(() => setPinDropped(true), 150);
    return () => clearTimeout(dropTimer);
  }, [isLoading, visible]);

  // Phase 2 -> Phase 3: after the pin has landed and held, unmount.
  useEffect(() => {
    if (!pinDropped) return undefined;

    const exitTimer = setTimeout(() => {
      setVisible(false);
    }, PIN_HOLD_MS);

    return () => clearTimeout(exitTimer);
  }, [pinDropped]);

  if (!visible) return null;

  return (
    <AnimatePresence onExitComplete={onComplete}>
      {visible && (
        <motion.div
          key="spatial-loader-overlay"
          className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/90 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 1.05 }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
        >
          <div
            className="relative flex items-center justify-center"
            style={{ width: RADAR_SIZE, height: RADAR_SIZE }}
          >
            {/* Phase 1: radar face + sweep + blips, fades as the pin arrives */}
            <motion.div
              className="absolute inset-0"
              animate={{ opacity: pinDropped ? 0 : 1, scale: pinDropped ? 0.85 : 1 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
            >
              <RadarFace blips={blips} active={isLoading} />
            </motion.div>

            {/* Phase 2: MapPin drops into the center once loading completes */}
            <AnimatePresence>
              {pinDropped && (
                <motion.div
                  key="map-pin"
                  className="absolute flex items-center justify-center"
                  initial={{ y: -180, opacity: 0, scale: 0.6 }}
                  animate={{ y: 0, opacity: 1, scale: 1 }}
                  transition={{ type: "spring", bounce: 0.4, duration: 0.9 }}
                >
                  <div className="relative flex items-center justify-center">
                    <motion.span
                      className="absolute h-16 w-16 rounded-full bg-cyan-400/20"
                      initial={{ scale: 0.3, opacity: 0.8 }}
                      animate={{ scale: 2.2, opacity: 0 }}
                      transition={{ duration: 0.7, ease: "easeOut", delay: 0.15 }}
                    />
                    <MapPin
                      className="h-16 w-16 text-cyan-400 drop-shadow-[0_0_12px_rgba(34,211,238,0.65)]"
                      strokeWidth={1.75}
                      fill="rgba(34,211,238,0.15)"
                    />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Status text */}
          <div className="mt-8 h-6 text-center">
            <AnimatePresence mode="wait">
              {!pinDropped ? (
                <motion.p
                  key={SCAN_PHRASES[phraseIndex]}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.3 }}
                  className="text-sm font-medium tracking-wide text-slate-300"
                >
                  {SCAN_PHRASES[phraseIndex]}
                </motion.p>
              ) : (
                <motion.p
                  key="locations-mapped"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: 0.25 }}
                  className="text-sm font-semibold tracking-wide text-cyan-300"
                >
                  Locations Mapped!
                </motion.p>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/**
 * RadarFace: rings, rotating sweep gradient, and randomly-timed blips.
 * Pure presentational piece, isolated so SpatialLoader stays readable.
 */
function RadarFace({ blips, active }) {
  const ringRadii = [130, 95, 60];

  return (
    <svg
      viewBox={`0 0 ${RADAR_SIZE} ${RADAR_SIZE}`}
      className="h-full w-full"
      role="img"
      aria-label="Scanning for place names"
    >
      <defs>
        <radialGradient id="radar-face-fill" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(34,211,238,0.10)" />
          <stop offset="100%" stopColor="rgba(34,211,238,0)" />
        </radialGradient>
        <linearGradient id="radar-sweep-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="rgba(34,211,238,0)" />
          <stop offset="100%" stopColor="rgba(34,211,238,0.55)" />
        </linearGradient>
      </defs>

      {/* Soft fill behind everything */}
      <circle cx={RADAR_CENTER} cy={RADAR_CENTER} r={ringRadii[0]} fill="url(#radar-face-fill)" />

      {/* Concentric rings, each pulsing gently and independently */}
      {ringRadii.map((r, i) => (
        <motion.circle
          key={r}
          cx={RADAR_CENTER}
          cy={RADAR_CENTER}
          r={r}
          fill="none"
          stroke="rgba(148,163,184,0.35)"
          strokeWidth={1}
          animate={
            active
              ? { opacity: [0.35, 0.7, 0.35], scale: [1, 1.015, 1] }
              : { opacity: 0.35, scale: 1 }
          }
          transition={{
            duration: 2.6,
            repeat: active ? Infinity : 0,
            ease: "easeInOut",
            delay: i * 0.25,
          }}
        />
      ))}

      {/* Crosshair lines */}
      <line
        x1={RADAR_CENTER}
        y1={RADAR_CENTER - ringRadii[0]}
        x2={RADAR_CENTER}
        y2={RADAR_CENTER + ringRadii[0]}
        stroke="rgba(148,163,184,0.18)"
        strokeWidth={1}
      />
      <line
        x1={RADAR_CENTER - ringRadii[0]}
        y1={RADAR_CENTER}
        x2={RADAR_CENTER + ringRadii[0]}
        y2={RADAR_CENTER}
        stroke="rgba(148,163,184,0.18)"
        strokeWidth={1}
      />

      {/* Rotating sweep, clipped to the outer ring */}
      <clipPath id="radar-clip">
        <circle cx={RADAR_CENTER} cy={RADAR_CENTER} r={ringRadii[0]} />
      </clipPath>

      <motion.g
        clipPath="url(#radar-clip)"
        style={{ transformOrigin: `${RADAR_CENTER}px ${RADAR_CENTER}px` }}
        animate={active ? { rotate: 360 } : { rotate: 0 }}
        transition={{ duration: 2.2, repeat: active ? Infinity : 0, ease: "linear" }}
      >
        <path
          d={`M ${RADAR_CENTER} ${RADAR_CENTER} L ${RADAR_CENTER} ${
            RADAR_CENTER - ringRadii[0]
          } A ${ringRadii[0]} ${ringRadii[0]} 0 0 1 ${
            RADAR_CENTER + ringRadii[0] * Math.sin((Math.PI / 180) * 70)
          } ${RADAR_CENTER - ringRadii[0] * Math.cos((Math.PI / 180) * 70)} Z`}
          fill="url(#radar-sweep-gradient)"
        />
      </motion.g>

      {/* Blips: tiny glowing dots that pop up at staggered times */}
      {blips.map((blip) => (
        <motion.circle
          key={blip.id}
          cx={blip.x}
          cy={blip.y}
          r={4}
          fill="#22d3ee"
          initial={{ opacity: 0, scale: 0 }}
          animate={
            active
              ? { opacity: [0, 1, 1, 0], scale: [0, 1.3, 1, 0.8] }
              : { opacity: 0, scale: 0 }
          }
          transition={{
            duration: 1.6,
            repeat: active ? Infinity : 0,
            repeatDelay: 1.6 + Math.random() * 1.4,
            delay: blip.delay,
            ease: "easeOut",
          }}
          style={{ filter: "drop-shadow(0 0 4px rgba(34,211,238,0.9))" }}
        />
      ))}

      {/* Center dot */}
      <circle cx={RADAR_CENTER} cy={RADAR_CENTER} r={3} fill="rgba(226,232,240,0.8)" />
    </svg>
  );
}
