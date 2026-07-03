"use client";

import { BarChart3, Cpu, LayoutDashboard, ScrollText, Users } from "lucide-react";
import { ResponsiveShell, type NavSection } from "@/components/ResponsiveShell";

const navSections: NavSection[] = [
  {
    title: "Principal",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      {
        href: "/clientes",
        label: "Clientes",
        icon: Users,
        match: (p) => p === "/clientes" || p.startsWith("/clientes/"),
      },
      { href: "/usage", label: "Métricas", icon: BarChart3 },
      {
        href: "/logs",
        label: "Logs",
        icon: ScrollText,
        match: (p) => p === "/logs",
      },
    ],
  },
  {
    title: "Configurações",
    items: [{ href: "/settings/llm", label: "Modelos LLM", icon: Cpu }],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ResponsiveShell
      title="Harness Admin"
      subtitle="Plataforma SaaS"
      navSections={navSections}
      onLogout={() => {
        localStorage.removeItem("access_token");
        window.location.href = "/login";
      }}
      footer={
        <div className="mb-2 flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
            A
          </div>
          <span className="text-xs font-medium text-gray-700">Administrador</span>
        </div>
      }
      maxWidth="6xl"
    >
      {children}
    </ResponsiveShell>
  );
}

// Keep Sidebar export for backwards compatibility if needed elsewhere
export function Sidebar() {
  return null;
}
