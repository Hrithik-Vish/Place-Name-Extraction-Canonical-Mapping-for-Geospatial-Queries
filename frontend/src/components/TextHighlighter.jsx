import { useEffect, useState } from 'react';
import {
  Loader2,
  Sparkles,
  FileText,
  AlertCircle,
} from 'lucide-react';

import ResolveLoader from './ResolveLoader';

const TextHighlighter = ({
  onExtract,
  isExtracting,
}) => {
  const [inputText, setInputText] =
    useState('');

  const [validationError, setValidationError] =
    useState('');

  // Decoupled from isExtracting on purpose. isExtracting flips to false the
  // instant the request settles, but ResolveLoader still has its own
  // settle -> hold -> fade-out sequence left to play. If the textarea swap
  // (and the extract button's disabled/label state) were driven directly
  // off isExtracting, the loader would get yanked out mid-animation the
  // moment data arrives instead of finishing its exit. showLoader stays
  // true until ResolveLoader itself reports (via onSettled) that its exit
  // transition has actually completed, so the swap-back only happens once
  // there's nothing left on screen to interrupt.
  const [showLoader, setShowLoader] = useState(isExtracting);

  useEffect(() => {
    if (isExtracting) {
      setShowLoader(true);
    }
  }, [isExtracting]);

  const handleLoaderSettled = () => {
    setShowLoader(false);
  };

  const handleClear = () => {
    setInputText('');
    setValidationError('');
  };

  const handleSubmit = () => {
    const trimmedText =
      inputText.trim();

    if (!trimmedText) {
      setValidationError(
        'Please enter some text before submitting.'
      );
      return;
    }

    setValidationError('');
    onExtract(trimmedText);
  };

  const handleChange = (event) => {
    setInputText(
      event.target.value
    );

    if (
      event.target.value.trim()
    ) {
      setValidationError('');
    }
  };

  return (
    <div className="panel-card input-panel">
      <div className="panel-heading">
        <div className="panel-heading-icon blue">
          <FileText size={19} />
        </div>

        <div>
          <h2>
            Text Analysis
          </h2>

          <p>
            Extract historical place
            names automatically
          </p>
        </div>
      </div>

      <div className="input-label-row">
        <label>
          Source Text
        </label>

        <div className="input-actions">
          <button
            type="button"
            onClick={handleClear}
            disabled={
              showLoader
            }
          >
            Clear
          </button>
        </div>
      </div>

      <div className="analysis-input-wrapper">
        {showLoader ? (
          <ResolveLoader
            isLoading={isExtracting}
            onSettled={handleLoaderSettled}
          />
        ) : (
          <textarea
            className={`analysis-textarea ${
              validationError
                ? 'input-error'
                : ''
            }`}
            value={inputText}
            onChange={handleChange}
            placeholder="Paste historical documents, archival text, letters or other content here..."
            disabled={isExtracting}
          />
        )}
      </div>

      <div className="input-footer">
        <span>
          {inputText.length} characters
        </span>

        <span>
          AI-powered place extraction
        </span>
      </div>

      {validationError && (
        <div className="validation-message">
          <AlertCircle size={15} />

          <span>
            {validationError}
          </span>
        </div>
      )}

      <button
        className="extract-button"
        onClick={handleSubmit}
        disabled={showLoader}
      >
        {showLoader ? (
          <>
            <Loader2
              size={18}
              className="animate-spin"
            />

            Processing document...
          </>
        ) : (
          <>
            <Sparkles size={18} />

            Extract & Map Places
          </>
        )}
      </button>
    </div>
  );
};

export default TextHighlighter;