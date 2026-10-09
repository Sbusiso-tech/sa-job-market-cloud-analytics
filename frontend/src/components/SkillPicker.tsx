import { useId, useState } from 'react';
import type { SkillListItem } from '../api/types';

interface SkillPickerProps {
  skills: SkillListItem[];
  selected: string[];
  onChange: (next: string[]) => void;
  max: number;
  disabled?: boolean;
}

/** Multi-select of known skills as toggle chips, grouped by category, with a search box. */
export function SkillPicker({ skills, selected, onChange, max, disabled }: SkillPickerProps) {
  const [query, setQuery] = useState('');
  const searchId = useId();
  const statusId = useId();
  const full = selected.length >= max;
  const q = query.trim().toLowerCase();
  const visible = skills.filter((s) => !q || s.name.toLowerCase().includes(q) || s.category.toLowerCase().includes(q));
  const byCategory = new Map<string, SkillListItem[]>();
  for (const s of visible) byCategory.set(s.category, [...(byCategory.get(s.category) ?? []), s]);

  function toggle(name: string) {
    if (selected.includes(name)) onChange(selected.filter((s) => s !== name));
    else if (!full) onChange([...selected, name]);
  }

  return (
    <fieldset className="skill-picker" disabled={disabled} aria-describedby={statusId}>
      <legend>Skills</legend>
      <p id={statusId} className="skill-picker__status" aria-live="polite">
        {selected.length} of {max} selected
        {full && ' (maximum reached)'}
      </p>
      {selected.length > 0 && (
        <div className="chip-row skill-picker__selected">
          {selected.map((name) => (
            <button key={name} type="button" className="chip chip--selected" onClick={() => toggle(name)}>
              {name} <span aria-hidden="true">×</span>
              <span className="visually-hidden">remove</span>
            </button>
          ))}
        </div>
      )}
      <label htmlFor={searchId} className="visually-hidden">
        Search skills
      </label>
      <input
        id={searchId}
        type="search"
        placeholder="Search skills, e.g. Python or Cloud"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="skill-picker__groups">
        {[...byCategory.entries()].map(([category, items]) => (
          <div key={category} className="skill-picker__group">
            <span className="skill-picker__category">{category}</span>
            <div className="chip-row">
              {items.map((s) => {
                const on = selected.includes(s.name);
                return (
                  <button
                    key={s.name}
                    type="button"
                    className={on ? 'chip chip--toggle chip--selected' : 'chip chip--toggle'}
                    aria-pressed={on}
                    disabled={!on && full}
                    onClick={() => toggle(s.name)}
                  >
                    {s.name}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
        {visible.length === 0 && <p className="muted">No skills match “{query}”.</p>}
      </div>
    </fieldset>
  );
}
