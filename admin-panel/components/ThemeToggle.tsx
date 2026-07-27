"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    const stored = localStorage.getItem("theme");
    if (stored === "system") {
      setTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    }
  }, [mounted, setTheme]);

  const isDark = mounted && resolvedTheme === "dark";

  const toggle = () => {
    setTheme(isDark ? "light" : "dark");
  };

  const Icon = isDark ? Moon : Sun;
  const label = !mounted ? "Tema" : isDark ? "Escuro" : "Claro";

  if (compact) {
    return (
      <button
        type="button"
        onClick={toggle}
        className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-gray-600 transition hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
        aria-label={`Tema: ${label}. Alternar tema`}
        title={`Tema: ${label}`}
      >
        <Icon className="h-5 w-5" strokeWidth={2} />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="mb-2 flex w-full items-center gap-2.5 rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
      aria-label={`Tema: ${label}. Alternar tema`}
      title={`Tema: ${label}`}
    >
      <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
      Tema: {label}
    </button>
  );
}
