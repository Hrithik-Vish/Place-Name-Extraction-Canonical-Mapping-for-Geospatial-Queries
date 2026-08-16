import { useState } from 'react';
import {
  Loader2,
  Sparkles,
  FileText,
  AlertCircle,
} from 'lucide-react';

const TextHighlighter = ({
  onExtract,
  isExtracting,
}) => {
  const [inputText, setInputText] =
    useState('');

  const [validationError, setValidationError] =
    useState('');

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
              isExtracting
            }
          >
            Clear
          </button>
        </div>
      </div>

      <div
        className={`analysis-input-wrapper ${
          isExtracting
            ? 'is-scanning'
            : ''
        }`}
      >
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

        {isExtracting && (
          <>
            <div className="scan-line" />

            <div className="scan-status">
              <Loader2
                size={15}
                className="animate-spin"
              />

              <span>
                AI is scanning the
                document...
              </span>
            </div>
          </>
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
        disabled={isExtracting}
      >
        {isExtracting ? (
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