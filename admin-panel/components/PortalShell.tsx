"use client";

import { BookOpen, LayoutDashboard, MessageSquare } from "lucide-react";
import { ResponsiveShell, type NavSection } from "@/components/ResponsiveShell";

const navSections: NavSection[] = [
  {
    title: "Principal",
    items: [
      { href: "/portal", label: "Visão geral", icon: LayoutDashboard },
      { href: "/portal/prompts", label: "Prompts", icon: MessageSquare },
      { href: "/portal/knowledge", label: "Conhecimento", icon: BookOpen },
    ],
  },
];

export function PortalShell({ children }: { children: React.ReactNode }) {
  return (
    <ResponsiveShell
      title="Portal do Cliente"
      subtitle="Gerencie seu chatbot"
      navSections={navSections}
      onLogout={() => {
        localStorage.removeItem("portal_access_token");
        window.location.href = "/portal/login";
      }}
      maxWidth="5xl"
    >
      {children}
    </ResponsiveShell>
  );
}
