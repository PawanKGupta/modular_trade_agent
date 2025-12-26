import { useState } from 'react';

export interface DateRange {
  startDate: string; // YYYY-MM-DD format
  endDate: string; // YYYY-MM-DD format
}

export interface DateRangePickerProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
  className?: string;
}

// SVG Calendar Icon Component
function CalendarIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

const PRESET_RANGES = [
  { label: '7 Days', days: 7 },
  { label: '30 Days', days: 30 },
  { label: '90 Days', days: 90 },
  { label: '1 Year', days: 365 },
] as const;

function formatDateForInput(date: Date): string {
  return date.toISOString().split('T')[0];
}

function subtractDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() - days);
  return result;
}

export function DateRangePicker({ value, onChange, className = '' }: DateRangePickerProps) {
  const [showPresets, setShowPresets] = useState(false);

  const handlePresetClick = (days: number) => {
    const endDate = new Date();
    const startDate = subtractDays(endDate, days - 1); // Include today

    onChange({
      startDate: formatDateForInput(startDate),
      endDate: formatDateForInput(endDate),
    });
    setShowPresets(false);
  };

  const handleAllTimeClick = () => {
    // Set to a far past date (5 years ago)
    const endDate = new Date();
    const startDate = subtractDays(endDate, 365 * 5);

    onChange({
      startDate: formatDateForInput(startDate),
      endDate: formatDateForInput(endDate),
    });
    setShowPresets(false);
  };

  return (
    <div className={`relative inline-flex flex-col gap-2 ${className}`}>
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-2">
          <CalendarIcon className="w-4 h-4 text-gray-500" />
          <label htmlFor="start-date" className="text-sm text-gray-700">
            From:
          </label>
          <input
            id="start-date"
            type="date"
            value={value.startDate}
            onChange={(e) => onChange({ ...value, startDate: e.target.value })}
            max={value.endDate}
            className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="end-date" className="text-sm text-gray-700">
            To:
          </label>
          <input
            id="end-date"
            type="date"
            value={value.endDate}
            onChange={(e) => onChange({ ...value, endDate: e.target.value })}
            min={value.startDate}
            max={formatDateForInput(new Date())}
            className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <button
          type="button"
          onClick={() => setShowPresets(!showPresets)}
          className="px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
        >
          Presets ▾
        </button>
      </div>

      {showPresets && (
        <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-md shadow-lg z-10 min-w-[150px]">
          <div className="py-1">
            {PRESET_RANGES.map((preset) => (
              <button
                key={preset.days}
                type="button"
                onClick={() => handlePresetClick(preset.days)}
                className="w-full px-4 py-2 text-left text-sm hover:bg-gray-100 transition-colors"
              >
                {preset.label}
              </button>
            ))}
            <button
              type="button"
              onClick={handleAllTimeClick}
              className="w-full px-4 py-2 text-left text-sm hover:bg-gray-100 transition-colors border-t border-gray-200"
            >
              All Time
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
