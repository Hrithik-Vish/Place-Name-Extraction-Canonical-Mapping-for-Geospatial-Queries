import { useEffect, useRef, useState } from 'react';
import { MapPin, Radar } from 'lucide-react';

// Mirrors the real backend pipeline stages (extraction -> local lookup ->
// Nominatim fallback / disambiguation) so the copy is honest about what's
// actually happening, not just generic "loading..." filler.
const PIPELINE_PHRASES = [
  'Extracting place names...',
  'Matching against local gazetteer...',
  'Resolving coordinates...',
];

const PHRASE_INTERVAL_MS = 1300;
const SETTLE_HOLD_MS = 650; // time "Locations mapped" is shown before handing back to the caller

/**
 * ResolveLoader
 *
 * Scoped loading animation for the active waiting window between
 * submitting text and the response rendering. Lives inside the analysis
 * panel (not a full-page overlay) so the sidebar, header, and stat cards
 * stay visible and usable while a request is in flight, matching how
 * `isExtracting` already behaves elsewhere in this app.
 *
 * Props:
 *  - isLoading: boolean   Drives the scanning phase. Required.
 *  - onSettled: () => void  Optional. Called once the brief "settled" hold
 *                            finishes after isLoading flips false — use
 *                            this only if something needs to happen after
 *                            the visual settle beat, not to gate whether
 *                            results render (App.jsx already renders
 *                            results independently once data arrives).
 *
 * This component never leaves itself in a stuck state: every visual phase
 * is driven directly off isLoading via effects that clean up on unmount,
 * and the exit uses a real CSS transition (via onTransitionEnd) rather
 * than a fixed setTimeout guess, so it can't desync from what's on screen
 * even if isLoading flips again mid-animation.
 */
export default function ResolveLoader({ isLoading, onSettled }) {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [settled, setSettled] = useState(false);
  const [mounted, setMounted] = useState(isLoading);
  const [exiting, setExiting] = useState(false);

  const settleTimerRef = useRef(null);
  const wrapperRef = useRef(null);

  // Mount immediately when loading starts; reset settle/exit state so a
  // second submission (before this component fully unmounts) restarts
  // cleanly instead of inheriting stale animation state.
  useEffect(() => {
    if (isLoading) {
      setMounted(true);
      setExiting(false);
      setSettled(false);
      setPhraseIndex(0);
    }
  }, [isLoading]);

  // Cycle the pipeline phrase only while actively scanning.
  useEffect(() => {
    if (!isLoading || settled) return undefined;

    const id = setInterval(() => {
      setPhraseIndex((previous) => (previous + 1) % PIPELINE_PHRASES.length);
    }, PHRASE_INTERVAL_MS);

    return () => clearInterval(id);
  }, [isLoading, settled]);

  // isLoading -> false: show the "settled" (pin) state for a short, fixed
  // hold, then begin the exit transition. This timer only ever fires once
  // per loading run because isLoading flipping back to true resets
  // `settled` to false above, so there's no path where this fires twice
  // or fires after the component should already be gone.
  useEffect(() => {
    if (isLoading || !mounted || settled) return undefined;

    settleTimerRef.current = setTimeout(() => {
      setSettled(true);
    }, 50); // let the "no longer loading" render commit before settling

    return () => clearTimeout(settleTimerRef.current);
  }, [isLoading, mounted, settled]);

  useEffect(() => {
    if (!settled) return undefined;

    const holdTimer = setTimeout(() => {
      setExiting(true);
    }, SETTLE_HOLD_MS);

    return () => clearTimeout(holdTimer);
  }, [settled]);

  // Real transitionend listener drives the actual unmount, so the fade
  // this fires on is the fade the user is actually seeing — no fixed
  // delay that can drift out of sync with the CSS and leave a frozen
  // final frame on screen if timing in this file ever changes.
  useEffect(() => {
    const node = wrapperRef.current;
    if (!exiting || !node) return undefined;

    const handleTransitionEnd = (event) => {
      if (event.target !== node) return;
      setMounted(false);
      setExiting(false);
      setSettled(false);
      onSettled?.();
    };

    node.addEventListener('transitionend', handleTransitionEnd);
    return () => node.removeEventListener('transitionend', handleTransitionEnd);
  }, [exiting, onSettled]);

  if (!mounted) return null;

  return (
    <div
      ref={wrapperRef}
      className={`resolve-loader ${exiting ? 'is-exiting' : ''}`}
      role="status"
      aria-live="polite"
    >
      <div className="resolve-loader-visual">
        <div className={`resolve-loader-rings ${settled ? 'is-settled' : ''}`}>
          <span className="resolve-loader-ring" />
          <span className="resolve-loader-ring" />
          <span className="resolve-loader-ring" />

          <div className="resolve-loader-sweep" />

          <div className="resolve-loader-icon">
            {settled ? (
              <MapPin size={26} className="resolve-loader-pin" strokeWidth={2} />
            ) : (
              <Radar size={24} strokeWidth={2} />
            )}
          </div>
        </div>
      </div>

      <p className="resolve-loader-text">
        {settled ? 'Locations mapped' : PIPELINE_PHRASES[phraseIndex]}
      </p>
    </div>
  );
}
