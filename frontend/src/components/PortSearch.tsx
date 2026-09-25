import { useEffect, useMemo, useRef, useState } from "react";
import { MapPin, Search, X } from "lucide-react";
import type { Port } from "../types";

interface PortSearchProps {
  label: string;
  value: Port | null;
  onChange: (port: Port | null) => void;
  ports: Port[];
  loading?: boolean;
  /** Port id to grey out — used to stop origin and destination matching. */
  excludePortId?: string | null;
  placeholder?: string;
  error?: string | null;
}

/**
 * Searchable port selector.
 *
 * The full Indian port dataset is a few dozen records, so it is fetched once
 * by the parent and filtered locally here — that keeps every keystroke
 * instant and avoids a network round trip per character. (The backend still
 * supports `?search=` for the day the dataset outgrows this approach.)
 *
 * Implements the combobox keyboard contract: ArrowDown/ArrowUp move the
 * active option, Enter selects it, Escape closes, Tab leaves. The listbox is
 * wired with aria-activedescendant so screen readers follow the highlight.
 */
export default function PortSearch({
  label,
  value,
  onChange,
  ports,
  loading = false,
  excludePortId = null,
  placeholder = "Search Indian port...",
  error = null,
}: PortSearchProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const inputId = `port-search-${label.replace(/\s+/g, "-").toLowerCase()}`;
  const listboxId = `${inputId}-listbox`;

  // Matches on name, state or UN/LOCODE so "Tamil Nadu", "chenn" and
  // "INMAA" all find Chennai Port.
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pool = ports.filter((p) => p.id !== excludePortId);
    if (!q) return pool;
    return pool.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.state.toLowerCase().includes(q) ||
        (p.port_code ?? "").toLowerCase().includes(q)
    );
  }, [ports, query, excludePortId]);

  // Keep the highlight in range as the filtered list shrinks.
  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  // Close when focus or a click moves outside the component.
  useEffect(() => {
    function onPointerDown(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  // Keep the active option scrolled into view during arrow navigation.
  useEffect(() => {
    if (!open || !listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>(`[data-index="${activeIndex}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open]);

  function select(port: Port) {
    onChange(port);
    setQuery("");
    setOpen(false);
    inputRef.current?.blur();
  }

  function clear() {
    onChange(null);
    setQuery("");
    setOpen(true);
    inputRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setActiveIndex((i) => Math.min(i + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      if (open && matches[activeIndex]) {
        e.preventDefault();
        select(matches[activeIndex]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    } else if (e.key === "Home" && open) {
      e.preventDefault();
      setActiveIndex(0);
    } else if (e.key === "End" && open) {
      e.preventDefault();
      setActiveIndex(matches.length - 1);
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <label
        htmlFor={inputId}
        className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500"
      >
        {label}
      </label>

      {value ? (
        // Selected state: show the chosen port as a chip with a clear button.
        <div
          className={`flex items-center justify-between gap-2 rounded-md border px-3 py-2 ${
            error ? "border-red-300 bg-red-50" : "border-deepblue/40 bg-deepblue/5"
          }`}
        >
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-ink">{value.name}</div>
            <div className="truncate text-xs text-slate-500">
              {value.state} · {value.port_type}
              {value.port_code ? ` · ${value.port_code}` : ""}
            </div>
          </div>
          <button
            type="button"
            onClick={clear}
            aria-label={`Clear ${label}`}
            className="shrink-0 rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-ink"
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <div className="relative">
          <Search
            size={15}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            id={inputId}
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded={open}
            aria-controls={listboxId}
            aria-autocomplete="list"
            aria-activedescendant={
              open && matches[activeIndex] ? `${listboxId}-opt-${activeIndex}` : undefined
            }
            autoComplete="off"
            className={`w-full rounded-md border px-3 py-2 pl-9 text-sm outline-none focus:ring-2 focus:ring-deepblue/30 ${
              error ? "border-red-300" : "border-slate-200"
            }`}
            placeholder={loading ? "Loading ports…" : placeholder}
            value={query}
            disabled={loading}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={handleKeyDown}
          />
        </div>
      )}

      {error && <p className="mt-1 text-xs font-medium text-red-600">{error}</p>}

      {open && !value && (
        <ul
          id={listboxId}
          ref={listRef}
          role="listbox"
          aria-label={`${label} results`}
          className="absolute z-[1000] mt-1 max-h-64 w-full overflow-auto rounded-md border border-slate-200 bg-white py-1 shadow-lg"
        >
          {matches.length === 0 && (
            <li className="px-3 py-3 text-sm text-slate-400">
              No ports match “{query}”.
            </li>
          )}

          {matches.map((port, i) => (
            <li
              key={port.id}
              id={`${listboxId}-opt-${i}`}
              data-index={i}
              role="option"
              aria-selected={i === activeIndex}
              // onMouseDown, not onClick: mousedown fires before the input's
              // blur, so the list is still mounted when the choice registers.
              onMouseDown={(e) => {
                e.preventDefault();
                select(port);
              }}
              onMouseEnter={() => setActiveIndex(i)}
              className={`flex cursor-pointer items-start gap-2 px-3 py-2 ${
                i === activeIndex ? "bg-deepblue/10" : ""
              }`}
            >
              <MapPin
                size={14}
                className={`mt-0.5 shrink-0 ${
                  port.port_type === "Major Port" ? "text-deepblue" : "text-slate-400"
                }`}
              />
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-ink">{port.name}</div>
                <div className="truncate text-xs text-slate-500">
                  {port.state} · {port.port_type}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
