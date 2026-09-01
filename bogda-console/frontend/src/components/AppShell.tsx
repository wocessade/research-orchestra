import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";

import { api } from "../api/client";
import type { CapabilitySnapshot } from "../api/types";
import { BrandMark } from "./BrandMark";


const destinations = [
  { to: "/", label: "总览", glyph: "⌂" },
  { to: "/runs", label: "运行", glyph: "↗" },
  { to: "/reviews", label: "评审", glyph: "◇" },
  { to: "/infrastructure", label: "基础设施", glyph: "⌘" },
  { to: "/decisions", label: "决策", glyph: "!" },
  { to: "/model-policy", label: "模型策略", glyph: "◌" },
];


function Navigation({ mobile = false }: { mobile?: boolean }) {
  return (
    <nav className={mobile ? "mobile-nav" : "rail-nav"} aria-label={mobile ? "移动主导航" : "主导航"}>
      {destinations.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.to === "/"}>
          <span aria-hidden="true" className="nav-glyph">{item.glyph}</span>
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}


export function AppShell({ children }: { children: ReactNode }) {
  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api.get<CapabilitySnapshot>("/api/v1/capabilities"),
  });
  const publicPort = capabilities.data?.data?.publicPort ?? 3101;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <aside className="app-rail">
        <BrandMark />
        <Navigation />
        <div className="rail-foot">
          <span className="source-dot" aria-hidden="true" />
          <span><strong>{publicPort} 影子运行</strong><small>影子控制台 · 不写现网 Prefect</small></span>
        </div>
      </aside>
      <main id="main-content" tabIndex={-1}>{children}</main>
      <Navigation mobile />
    </div>
  );
}
