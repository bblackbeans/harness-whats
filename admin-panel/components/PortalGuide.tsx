import Link from "next/link";
import { HelpTip } from "@/components/HelpTip";

type PortalGuideProps = {
  title: string;
  children: React.ReactNode;
  className?: string;
};

export function PortalGuide({ title, children, className = "" }: PortalGuideProps) {
  return (
    <div className={`rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-300 ${className}`}>
      <p className="font-medium text-gray-900 dark:text-gray-100">{title}</p>
      <div className="mt-2 space-y-2">{children}</div>
    </div>
  );
}

type PortalLegendProps = {
  title?: string;
  items: Array<{ color: string; label: string; text: string }>;
  footer?: string;
};

const LEGEND_COLORS: Record<string, string> = {
  blue: "bg-blue-500",
  green: "bg-green-500",
  amber: "bg-amber-500",
  gray: "bg-gray-500",
};

export function PortalLegend({ title = "Como funciona", items, footer }: PortalLegendProps) {
  return (
    <div className="card text-sm text-gray-600 dark:text-gray-300">
      <p className="mb-3 font-medium text-gray-900 dark:text-gray-100">{title}</p>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.label} className="flex gap-2">
            <span
              className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${LEGEND_COLORS[item.color] || LEGEND_COLORS.gray}`}
            />
            <span>
              <strong className="text-gray-800 dark:text-gray-200">{item.label}</strong> — {item.text}
            </span>
          </li>
        ))}
      </ul>
      {footer && <p className="mt-3 border-t border-gray-200 pt-3 text-xs text-gray-500 dark:border-gray-800 dark:text-gray-400">{footer}</p>}
    </div>
  );
}

type PortalActionCardProps = {
  href: string;
  title: string;
  description: string;
};

export function PortalActionCard({ href, title, description }: PortalActionCardProps) {
  return (
    <Link
      href={href}
      className="card block transition hover:border-brand-300 hover:bg-brand-50/30 dark:hover:border-brand-600"
    >
      <p className="font-medium text-gray-900 dark:text-gray-100">{title}</p>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{description}</p>
      <p className="mt-2 text-sm font-medium text-brand-600">Abrir →</p>
    </Link>
  );
}

export function PortalHelpLabel({ label, help }: { label: string; help: string }) {
  if (!label) {
    return <HelpTip text={help} />;
  }
  return (
    <span className="inline-flex items-center gap-1 text-sm font-medium text-gray-700 dark:text-gray-300">
      {label}
      <HelpTip text={help} />
    </span>
  );
}
