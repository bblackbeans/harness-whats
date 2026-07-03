"use client";

import { useEffect, useRef, useState } from "react";
import { HelpCircle } from "lucide-react";

type HelpTipProps = {
  text: string;
  className?: string;
};

export function HelpTip({ text, className = "" }: HelpTipProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function toggle(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setOpen((v) => !v);
  }

  return (
    <span ref={ref} className={`relative inline-flex shrink-0 align-middle ${className}`}>
      <button
        type="button"
        className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-brand-600"
        aria-label="Ajuda"
        onClick={toggle}
        onMouseDown={(e) => e.preventDefault()}
      >
        <HelpCircle className="h-4 w-4" strokeWidth={2} />
      </button>
      {open && (
        <div
          role="tooltip"
          className="absolute left-0 top-full z-50 mt-2 w-[min(16rem,calc(100vw-2rem))] rounded-lg border border-gray-200 bg-white p-3 text-xs leading-relaxed text-gray-600 shadow-lg sm:left-full sm:top-1/2 sm:mt-0 sm:ml-2 sm:w-64 sm:-translate-y-1/2"
          onClick={(e) => e.stopPropagation()}
        >
          {text}
        </div>
      )}
    </span>
  );
}

type FieldLabelProps = {
  label: string;
  help: string;
  htmlFor?: string;
};

export function FieldLabel({ label, help, htmlFor }: FieldLabelProps) {
  return (
    <div className="mb-1.5 flex items-center gap-1 text-sm font-medium text-gray-700">
      <label htmlFor={htmlFor} className="cursor-default">
        {label}
      </label>
      <HelpTip text={help} />
    </div>
  );
}

type HelpButtonProps = {
  label: string;
  help: string;
  className?: string;
};

export function HelpButton({ label, help, className = "" }: HelpButtonProps) {
  return (
    <span className={`inline-flex items-center gap-1 ${className}`}>
      <span>{label}</span>
      <HelpTip text={help} />
    </span>
  );
}
