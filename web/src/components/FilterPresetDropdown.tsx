import React, { useState } from 'react';

type FilterPreset = Record<string, unknown>;

interface FilterPresetDropdownProps {
  presets: Record<string, FilterPreset>;
  onLoadPreset: (filters: FilterPreset) => void;
  onSavePreset: (name: string, filters: FilterPreset) => Promise<boolean>;
  onDeletePreset: (name: string) => Promise<boolean>;
  currentFilters: FilterPreset;
  loading?: boolean;
}

export function FilterPresetDropdown({
  presets,
  onLoadPreset,
  onSavePreset,
  onDeletePreset,
  currentFilters,
  loading = false,
}: FilterPresetDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isSaveMode, setIsSaveMode] = useState(false);
  const [newPresetName, setNewPresetName] = useState('');
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleLoadPreset = (presetName: string) => {
    const preset = presets[presetName];
    if (preset) {
      onLoadPreset(preset);
      setIsOpen(false);
    }
  };

  const handleSaveNew = async () => {
    if (!newPresetName.trim()) {
      setSaveError('Please enter a preset name');
      return;
    }

    if (presets[newPresetName]) {
      setSaveError('Preset name already exists');
      return;
    }

    const success = await onSavePreset(newPresetName.trim(), currentFilters);
    if (success) {
      setNewPresetName('');
      setIsSaveMode(false);
      setSaveError(null);
    } else {
      setSaveError('Failed to save preset');
    }
  };

  const handleDeletePreset = async (presetName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm(`Delete preset "${presetName}"?`)) {
      await onDeletePreset(presetName);
    }
  };

  const presetNames = Object.keys(presets);

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={loading}
        className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-[var(--text)] bg-[var(--panel)] border border-[#1e293b] rounded-md hover:bg-[#0f172a] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] disabled:opacity-50"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
          />
        </svg>
        Filter Presets
        {presetNames.length > 0 && (
          <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-[#0f172a] text-[var(--muted)] border border-[#1e293b]">
            {presetNames.length}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute left-0 z-10 mt-2 w-64 bg-[var(--panel)] rounded-md shadow-lg border border-[#1e293b]">
          <div className="py-1">
            {/* Save New Preset Section */}
            <div className="px-4 py-2 border-b border-[#1e293b]">
              {!isSaveMode ? (
                <button
                  type="button"
                  onClick={() => setIsSaveMode(true)}
                  className="w-full text-left text-sm text-[var(--text)] hover:opacity-90 font-medium"
                >
                  + Save Current Filters
                </button>
              ) : (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={newPresetName}
                    onChange={(e) => {
                      setNewPresetName(e.target.value);
                      setSaveError(null);
                    }}
                    placeholder="Preset name..."
                    className="w-full px-2 py-1 text-sm bg-[var(--panel)] text-[var(--text)] border border-[#1e293b] rounded focus:ring-1 focus:ring-[var(--accent)] focus:border-[var(--accent)]"
                    autoFocus
                  />
                  {saveError && <p className="text-xs text-red-400">{saveError}</p>}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={handleSaveNew}
                      disabled={loading}
                      className="flex-1 px-2 py-1 text-xs font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setIsSaveMode(false);
                        setNewPresetName('');
                        setSaveError(null);
                      }}
                      className="flex-1 px-2 py-1 text-xs font-medium text-[var(--text)] bg-[#0f172a] rounded hover:opacity-90"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Saved Presets List */}
            {presetNames.length === 0 ? (
              <div className="px-4 py-3 text-sm text-[var(--muted)] text-center">
                No saved presets
              </div>
            ) : (
              <div className="max-h-64 overflow-y-auto">
                {presetNames.map((name) => (
                  <div
                    key={name}
                    className="flex items-center justify-between px-4 py-2 hover:bg-[#0f172a] cursor-pointer group"
                    onClick={() => handleLoadPreset(name)}
                  >
                    <span className="text-sm text-[var(--text)] truncate flex-1">{name}</span>
                    <button
                      type="button"
                      onClick={(e) => handleDeletePreset(name, e)}
                      className="ml-2 p-1 text-red-400 opacity-0 group-hover:opacity-100 hover:bg-[rgba(239,68,68,0.12)] rounded transition-opacity"
                      title="Delete preset"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Click outside to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-0"
          onClick={() => {
            setIsOpen(false);
            setIsSaveMode(false);
            setNewPresetName('');
            setSaveError(null);
          }}
        />
      )}
    </div>
  );
}
