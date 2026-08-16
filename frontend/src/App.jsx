import React, { useState, useEffect } from "react";
import { AlertTriangle, MapPinOff, RotateCcw } from "lucide-react";

import InputForm from "./components/InputForm";
import SpatialLoader from "./components/SpatialLoader";
import {
  MOCK_SUCCESS_RESPONSE,
  MOCK_EMPTY_RESPONSE,
} from "./mocks/mockResponse";
// Developer toggle: flip to false once the real /resolve endpoint is live.
// While true, requests never leave the browser — mockResponse.js stands in.
const USE_MOCK = false;
const MOCK_DELAY_MS = 2500; // long enough for the SpatialLoader sequence to play out

/**
 * appState values:
 *  - "idle":        initial state, form is interactive, nothing resolved yet
 *  - "processing":  request in flight (or mock delay running); loader is showing
 *  - "resolved":    responseData is populated and ready to render
 *  - "error":       request failed; errorMessage is populated
 */
export default function App() {
  const [textInput, setTextInput] = useState("");
  const [appState, setAppState] = useState("idle");
  const [responseData, setResponseData] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  /**
   * Resolves place names for the given text, either against the real
   * backend or the local mock, depending on USE_MOCK. Never throws —
   * all failure paths land in the "error" appState.
   */
  const resolveText = async (text) => {
    setTextInput(text);
    setAppState("processing");
    setErrorMessage("");
    setResponseData(null);

    try {
      let data;

      if (USE_MOCK) {
        data = await fetchMockResolution(text);
      } else {
        data = await fetchRealResolution(text);
      }

      setResponseData(data);
      // appState transitions to "resolved" once SpatialLoader finishes its
      // exit animation and calls onComplete — see below. This keeps the
      // pin-drop/reveal sequence from being cut short by an instant swap.
    } catch (err) {
      console.error("PS-09 /resolve failed:", err);
      setErrorMessage(
        err instanceof Error
          ? err.message
          : "Something went wrong while resolving locations. Please try again.",
      );
      setAppState("error");
    }
  };

  /**
   * Fires once SpatialLoader's exit animation completes. If a response
   * is already sitting in responseData, we move to "resolved"; if the
   * fetch itself failed, appState is already "error" and this is a no-op.
   */
  const handleLoaderComplete = () => {
    setAppState((current) => (current === "processing" ? "resolved" : current));
  };

  const handleReset = () => {
    setTextInput("");
    setResponseData(null);
    setErrorMessage("");
    setAppState("idle");
  };

  const hasResults =
    appState === "resolved" && responseData?.extracted?.length > 0;
  const isEmptyResult =
    appState === "resolved" && responseData?.extracted?.length === 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <SpatialLoader
        // Drop isLoading to false as soon as responseData is populated
        isLoading={appState === "processing" && responseData === null}
        onComplete={handleLoaderComplete}
      />

      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-8 px-6 py-12 lg:flex-row">
        {/* Left rail: input form */}
        <aside className="w-full flex-shrink-0 lg:w-96">
          <h1 className="mb-1 text-xl font-semibold text-slate-100">
            Place-Name Extraction &amp; Mapping
          </h1>
          <p className="mb-6 text-sm text-slate-400">
            Paste a sentence or paragraph and we'll extract, disambiguate, and
            map every place name we find.
          </p>

          <InputForm
            onSubmit={resolveText}
            isProcessing={appState === "processing"}
          />

          {(appState === "resolved" || appState === "error") && (
            <button
              type="button"
              onClick={handleReset}
              className="mt-4 inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-slate-400 transition-colors hover:text-slate-200"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Start over
            </button>
          )}
        </aside>

        {/* Right pane: results / empty / error states */}
        <main className="flex-1">
          {appState === "idle" && <IdlePlaceholder />}

          {appState === "error" && (
            <ErrorBanner
              message={errorMessage}
              onRetry={() => resolveText(textInput)}
            />
          )}

          {isEmptyResult && (
            <EmptyResultState message={responseData?.message} />
          )}

          {hasResults && (
            // Placeholder for the Map Lead's map + results table.
            // responseData follows the PS-09 contract shape:
            //   { original_text, message, extracted: [{ raw, status, canonical, lat, long, confidence, reason, source }] }
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
              <h2 className="mb-1 text-sm font-semibold text-slate-200">
                Map &amp; Results Table
              </h2>
              <p className="mb-4 text-xs text-slate-500">
                Placeholder — the Map Lead will render the map and results table
                here using the props below.
              </p>
              <pre className="max-h-[60vh] overflow-auto rounded-xl bg-slate-950/60 p-4 text-xs text-slate-400">
                {JSON.stringify(responseData, null, 2)}
              </pre>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Fetch helpers                                                       */
/* ------------------------------------------------------------------ */

/**
 * Simulates the network round trip using local mock data. Text
 * containing the word "empty" (case-insensitive) resolves to the empty
 * response, so both edge cases are reachable during development without
 * touching this file.
 */
function fetchMockResolution(text) {
  return new Promise((resolve) => {
    setTimeout(() => {
      const useEmpty = /\bempty\b/i.test(text);
      const base = useEmpty ? MOCK_EMPTY_RESPONSE : MOCK_SUCCESS_RESPONSE;
      resolve({ ...base, original_text: text });
    }, MOCK_DELAY_MS);
  });
}

/** Real backend call, per the PS-09 API Contract. */
async function fetchRealResolution(text) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL;

  const response = await fetch(`${baseUrl}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    throw new Error(
      `Location resolution failed (status ${response.status}). Please try again in a moment.`,
    );
  }

  return response.json();
}

/* ------------------------------------------------------------------ */
/* Small presentational states                                         */
/* ------------------------------------------------------------------ */

function IdlePlaceholder() {
  return (
    <div className="flex h-full min-h-[320px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 text-center">
      <p className="max-w-xs text-sm text-slate-500">
        Results will appear here once you submit some text.
      </p>
    </div>
  );
}

function EmptyResultState({ message }) {
  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/40 px-6 text-center">
      <MapPinOff className="mb-4 h-10 w-10 text-slate-600" strokeWidth={1.5} />
      <h2 className="mb-1 text-base font-semibold text-slate-200">
        No locations detected
      </h2>
      <p className="max-w-sm text-sm text-slate-500">
        {message ||
          "We couldn't find any place names in that text. Try adding more context."}
      </p>
    </div>
  );
}

function ErrorBanner({ message, onRetry }) {
  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center rounded-2xl border border-rose-900/40 bg-rose-950/20 px-6 text-center">
      <AlertTriangle
        className="mb-4 h-10 w-10 text-rose-400"
        strokeWidth={1.5}
      />
      <h2 className="mb-1 text-base font-semibold text-rose-200">
        Something went wrong
      </h2>
      <p className="mb-5 max-w-sm text-sm text-rose-300/80">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-lg bg-rose-500/10 px-4 py-2 text-sm font-medium text-rose-200 transition-colors hover:bg-rose-500/20"
      >
        Try again
      </button>
    </div>
  );
}
