"use client";

import {
  BookOpen,
  Bot,
  FolderOpen,
  GitBranch,
  LayoutDashboard,
  Link2,
  MessageSquare,
  Contact,
  Tags,
  Waypoints,
  Wrench,
} from "lucide-react";
import { ResponsiveShell, type NavSection } from "@/components/ResponsiveShell";

const navSections: NavSection[] = [
  {
    title: "Principal",
    items: [
      { href: "/portal", label: "Visão geral", icon: LayoutDashboard },
      { href: "/portal/prompts", label: "Prompts", icon: MessageSquare },
      { href: "/portal/knowledge", label: "Conhecimento", icon: BookOpen },
      { href: "/portal/arquivos", label: "Arquivos", icon: FolderOpen },
    ],
  },
  {
    title: "CRM",
    items: [
      { href: "/portal/campos", label: "Campos", icon: Tags },
      { href: "/portal/contatos", label: "Contatos", icon: Contact },
      { href: "/portal/integracoes", label: "Integrações", icon: Link2 },
    ],
  },
  {
    title: "Automação",
    items: [
      { href: "/portal/orchestrator", label: "Orquestrador", icon: Waypoints },
      { href: "/portal/agents", label: "Agentes", icon: Bot },
      { href: "/portal/tools", label: "Tools", icon: Wrench },
      {
        href: "/portal/flows",
        label: "Flows",
        icon: GitBranch,
        disabled: true,
        disabledHint: "Flows fora do MVP — em breve",
      },
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
