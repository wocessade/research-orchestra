import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { BrandMark } from "./BrandMark";


const destinations = [
  { to: "/", label: "总览", glyph: "⌂" },
  { to: "/runs", label: "运行", glyph: "↗" },
  { to: "/reviews", label: "评审", glyph: "◇" },
  { to: "/infrastructure", label: "基础设施", glyph: "⌘" },
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
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <aside className="app-rail">
        <BrandMark />
        <Navigation />
        <div className="rail-foot">
          <span className="source-dot" aria-hidden="true" />
          <span><strong>3101 影子运行</strong><small>B · 受控操作 · 旧 3100 在线</small></span>
        </div>
      </aside>
      <main id="main-content" tabIndex={-1}>{children}</main>
      <Navigation mobile />
    </div>
  );
}
