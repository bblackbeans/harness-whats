"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { LogOut, Menu, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  match?: (pathname: string) => boolean;
};

export type NavSection = {
  title: string;
  items: NavItem[];
};

type ResponsiveShellProps = {
  title: string;
  subtitle: string;
  navSections: NavSection[];
  onLogout: () => void;
  footer?: React.ReactNode;
  children: React.ReactNode;
  maxWidth?: "5xl" | "6xl";
};

function NavLink({
  item,
  onNavigate,
}: {
  item: NavItem;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const active = item.match ? item.match(pathname) : pathname === item.href;
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={`nav-item ${active ? "nav-item-active" : ""}`}
    >
      <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={2} />
      <span>{item.label}</span>
    </Link>
  );
}

function SidebarContent({
  title,
  subtitle,
  navSections,
  onLogout,
  footer,
  onNavigate,
}: Omit<ResponsiveShellProps, "children" | "maxWidth"> & { onNavigate?: () => void }) {
  return (
    <>
      <div className="border-b border-gray-200 px-5 py-5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white shadow-sm">
            H
          </div>
          <div>
            <span className="block text-sm font-semibold text-gray-900">{title}</span>
            <span className="text-xs text-gray-500">{subtitle}</span>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-5">
        {navSections.map((section) => (
          <div key={section.title} className="mb-6">
            <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
              {section.title}
            </p>
            <div className="flex flex-col gap-0.5">
              {section.items.map((item) => (
                <NavLink key={item.href} item={item} onNavigate={onNavigate} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-gray-200 p-3">
        {footer}
        <button
          type="button"
          className="flex w-full items-center gap-2.5 rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm font-medium text-gray-700 transition hover:border-red-200 hover:bg-red-50 hover:text-red-700"
          onClick={onLogout}
        >
          <LogOut className="h-[18px] w-[18px]" strokeWidth={2} />
          Sair
        </button>
      </div>
    </>
  );
}

export function ResponsiveShell({
  title,
  subtitle,
  navSections,
  onLogout,
  footer,
  children,
  maxWidth = "6xl",
}: ResponsiveShellProps) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  const maxW = maxWidth === "5xl" ? "max-w-5xl" : "max-w-6xl";

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-gray-200 bg-white lg:flex">
        <SidebarContent
          title={title}
          subtitle={subtitle}
          navSections={navSections}
          onLogout={onLogout}
          footer={footer}
        />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 lg:hidden">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-xs font-bold text-white">
              H
            </div>
            <span className="text-sm font-semibold text-gray-900">{title}</span>
          </div>
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-gray-600 hover:bg-gray-100"
            aria-label={menuOpen ? "Fechar menu" : "Abrir menu"}
            onClick={() => setMenuOpen((v) => !v)}
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </header>

        {/* Mobile drawer — montado sempre em <lg para animação de entrada/saída */}
        <div
          className={`fixed inset-0 z-50 lg:hidden transition-opacity duration-300 ease-in-out motion-reduce:transition-none ${
            menuOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
          }`}
          aria-hidden={!menuOpen}
        >
          <div
            className="absolute inset-0 bg-black/40 transition-opacity duration-300 ease-in-out motion-reduce:transition-none"
            onClick={() => setMenuOpen(false)}
            aria-hidden
          />
          <aside
            role="dialog"
            aria-modal={menuOpen}
            aria-hidden={!menuOpen}
            className={`absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-white shadow-xl transition-transform duration-300 ease-in-out motion-reduce:transition-none motion-reduce:transform-none ${
              menuOpen ? "translate-x-0" : "-translate-x-full"
            }`}
          >
            <SidebarContent
              title={title}
              subtitle={subtitle}
              navSections={navSections}
              onLogout={onLogout}
              footer={footer}
              onNavigate={() => setMenuOpen(false)}
            />
          </aside>
        </div>

        <main className="flex-1 overflow-auto">
          <div className={`mx-auto ${maxW} px-4 py-4 sm:px-6 lg:px-8 lg:py-8`}>{children}</div>
        </main>
      </div>
    </div>
  );
}
