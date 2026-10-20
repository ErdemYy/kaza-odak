import { BarChart3, Database, FlaskConical, LayoutDashboard, Map as MapIcon, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import type { ComponentType } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { hashFor, ROUTES, useApp, type Route } from "../../app/store";

const ICONS: Record<Route, ComponentType<{ className?: string }>> = {
  overview: LayoutDashboard, explorer: MapIcon, lab: FlaskConical, models: BarChart3, data: Database,
};

export function Brand({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
        <rect width="32" height="32" rx="7" fill="#16233B" />
        <circle cx="16" cy="16" r="7.5" fill="none" stroke="#38BDF8" strokeWidth="2.5" />
        <circle cx="16" cy="16" r="2.6" fill="#F87171" />
      </svg>
      {!compact && (
        <div className="min-w-0">
          <div className="font-display font-bold text-[15px] leading-none tracking-tight">SafeRoute 3D</div>
          <div className="text-[11px] text-subtle leading-tight mt-1">NYC kaza analitiği</div>
        </div>
      )}
    </div>
  );
}

/** Ekran listesi; masaüstünde daraltılabilir kenar çubuğu, mobilde çekmece içinde aynı liste. */
export function NavList({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const route = useApp((s) => s.route);
  const setRoute = useApp((s) => s.setRoute);
  return (
    <ul className="space-y-1" role="list">
      {ROUTES.map((r) => {
        const Icon = ICONS[r.id];
        const active = route === r.id;
        const link = (
          <a href={hashFor(r.id)} aria-current={active ? "page" : undefined} data-route={r.id} aria-label={collapsed ? r.label : undefined}
            onClick={(e) => { e.preventDefault(); setRoute(r.id); onNavigate?.(); }}
            className={cn("group flex items-center gap-3 rounded-md px-2.5 h-10 text-[13.5px] font-semibold transition-colors outline-none",
              "focus-visible:ring-2 focus-visible:ring-ring",
              active ? "bg-primary/12 text-foreground" : "text-muted-foreground hover:bg-surface-2 hover:text-foreground",
              collapsed && "justify-center px-0")}>
            <span className={cn("relative flex size-5 items-center justify-center", active && "text-primary")}>
              <Icon className="size-[18px]" />
            </span>
            {!collapsed && <span className="truncate">{r.label}</span>}
            {active && !collapsed && <span className="ml-auto h-4 w-0.5 rounded-full bg-primary" aria-hidden />}
          </a>
        );
        return (
          <li key={r.id}>
            {collapsed ? (
              <Tooltip>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right">{r.label}</TooltipContent>
              </Tooltip>
            ) : link}
          </li>
        );
      })}
    </ul>
  );
}

export function Navigation() {
  const collapsed = useApp((s) => s.navCollapsed);
  const toggle = useApp((s) => s.toggleNav);
  return (
    <nav aria-label="Ana gezinme" data-testid="navigation" data-collapsed={collapsed}
      className={cn("hidden md:flex flex-col shrink-0 border-r border-line bg-surface transition-[width] duration-200",
        collapsed ? "w-[64px]" : "w-[248px]")}>
      <div className={cn("h-14 flex items-center border-b border-line", collapsed ? "justify-center" : "px-4")}>
        <Brand compact={collapsed} />
      </div>
      <div className="flex-1 overflow-y-auto scroll-thin p-2.5">
        <NavList collapsed={collapsed} />
      </div>
      <div className={cn("border-t border-line p-2.5", collapsed && "flex justify-center")}>
        <button type="button" onClick={toggle} data-testid="nav-toggle"
          aria-label={collapsed ? "Gezinmeyi genişlet" : "Gezinmeyi daralt"} aria-expanded={!collapsed}
          className="flex items-center gap-2 rounded-md h-9 px-2.5 text-[12.5px] font-semibold text-muted-foreground hover:bg-surface-2 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring outline-none">
          {collapsed ? <PanelLeftOpen className="size-4" /> : <><PanelLeftClose className="size-4" /> Daralt</>}
        </button>
      </div>
    </nav>
  );
}
