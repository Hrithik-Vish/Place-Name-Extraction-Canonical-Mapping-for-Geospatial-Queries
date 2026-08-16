// src/components/InputForm.jsx
import React from 'react';
import { useState } from "react";
import { Send, Loader2 } from "lucide-react";

/**
 * InputForm
 *
 * Props:
 *  - onSubmit: (text: string) => void   Called only with valid, trimmed text.
 *  - isProcessing: boolean              Disables input while a request is in flight.
 */
export default function InputForm({ onSubmit, isProcessing }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  const handleChange = (e) => {
    setValue(e.target.value);
    // Clear a stale error as soon as the user starts fixing it.
    if (error) setError("");
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    const trimmed = value.trim();

    if (!trimmed) {
      setError("Please enter text containing place names.");
      return;
    }

    setError("");
    onSubmit(trimmed);
  };

  const handleKeyDown = (e) => {
    // Cmd/Ctrl + Enter submits, since this is a multi-line field.
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xl">
      <label
        htmlFor="place-text-input"
        className="mb-2 block text-sm font-medium text-slate-300"
      >
        Paste text containing place names
      </label>

      <textarea
        id="place-text-input"
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        disabled={isProcessing}
        placeholder="e.g. We drove from Bengaluru through Hosur before stopping near Krishnagiri..."
        rows={6}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? "place-text-input-error" : undefined}
        className={`
          w-full resize-none rounded-xl border bg-slate-900/60 px-4 py-3
          text-sm leading-relaxed text-slate-100 placeholder:text-slate-500
          shadow-inner shadow-black/20 backdrop-blur-sm
          transition-colors duration-150
          focus:outline-none focus:ring-2 focus:ring-cyan-500/60
          disabled:cursor-not-allowed disabled:opacity-50
          ${error ? "border-rose-500/70" : "border-slate-700/80"}
        `}
      />

      {error && (
        <p
          id="place-text-input-error"
          role="alert"
          className="mt-2 text-sm text-rose-400"
        >
          {error}
        </p>
      )}

      <div className="mt-4 flex items-center justify-between">
        <span className="text-xs text-slate-500">
          ⌘/Ctrl + Enter to submit
        </span>

        <button
          type="submit"
          disabled={isProcessing}
          className={`
            inline-flex items-center gap-2 rounded-lg px-5 py-2.5
            text-sm font-semibold text-white
            shadow-lg shadow-cyan-950/40
            transition-all duration-150
            focus:outline-none focus:ring-2 focus:ring-cyan-500/60 focus:ring-offset-2 focus:ring-offset-slate-950
            disabled:cursor-not-allowed
            ${
              isProcessing
                ? "bg-slate-700 text-slate-300"
                : "bg-cyan-600 hover:bg-cyan-500 active:bg-cyan-700"
            }
          `}
        >
          {isProcessing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Send className="h-4 w-4" />
              Resolve Locations
            </>
          )}
        </button>
      </div>
    </form>
  );
}
