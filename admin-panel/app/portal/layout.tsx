"use client";

import { usePathname } from "next/navigation";
import { ReportProblemWidget } from "@/components/ReportProblemWidget";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/portal/login";

  return (
    <>
      {children}
      {!isLogin && <ReportProblemWidget />}
    </>
  );
}
