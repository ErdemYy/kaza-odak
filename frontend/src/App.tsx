// Uygulama kabuğu: sol gezinme + üst araç çubuğu + ekranlar. 3D şehir ekranı ilk açılışta kurulur ve
// ekranlar arasında geçerken KORUNUR (harita, WebGL bağlamı ve GLB'ler yeniden oluşturulmaz).
import { Menu } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { TooltipProvider } from "@/components/ui/tooltip";
import { LoadingBlock } from "./components/common";
import { Brand, Navigation, NavList } from "./components/layout/Navigation";
import { ROUTES, routeFromHash, useApp } from "./app/store";
import { ExplorerPage } from "./features/explorer/ExplorerPage";

const OverviewPage = lazy(() => import("./features/overview/OverviewPage"));
const LabPage = lazy(() => import("./features/lab/LabPage"));
const ModelsPage = lazy(() => import("./features/models/ModelsPage"));
const DataPage = lazy(() => import("./features/data/DataPage"));

export default function App() {
  const route = useApp((s) => s.route);
  const setRoute = useApp((s) => s.setRoute);
  const mobileSheet = useApp((s) => s.mobileSheet);
  const setMobileSheet = useApp((s) => s.setMobileSheet);
  const [explorerMounted, setExplorerMounted] = useState(route === "explorer");
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const onHash = () => setRoute(routeFromHash(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [setRoute]);

  const firstRoute = useRef(true);
  useEffect(() => {
    if (route === "explorer") setExplorerMounted(true);
    const r = ROUTES.find((x) => x.id === route)!;
    document.title = `${r.label} · SafeRoute 3D`;
    // Ekran değişiminde odak ana içeriğe taşınır (klavye ve ekran okuyucu kullanıcıları yeni ekranın başında olur)
    if (firstRoute.current) firstRoute.current = false;
    else mainRef.current?.focus({ preventScroll: true });
  }, [route]);

  const title = ROUTES.find((r) => r.id === route)!.label;
  const isExplorer = route === "explorer";

  return (
    <TooltipProvider delayDuration={250}>
      <a href="#main" className="skip-link" onClick={(e) => { e.preventDefault(); mainRef.current?.focus(); }}>İçeriğe geç</a>
      <div className="flex h-svh w-full overflow-hidden">
        <Navigation />
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Mobil üst çubuk: gezinme çekmecesi */}
          <div className="md:hidden flex h-12 shrink-0 items-center gap-2 border-b border-line bg-surface px-2">
            <Button variant="ghost" size="icon" aria-label="Menüyü aç" onClick={() => setMobileSheet("nav")} data-testid="mobile-menu">
              <Menu />
            </Button>
            <Brand compact />
            <span className="font-display font-bold text-[14px] truncate">{title}</span>
          </div>
          <main id="main" ref={mainRef} tabIndex={-1} className="relative min-h-0 flex-1 outline-none" aria-label={title}>
            {explorerMounted && (
              <div className={isExplorer ? "absolute inset-0" : "absolute inset-0 explorer-hidden"} aria-hidden={!isExplorer}
                data-testid="explorer-host">
                <ExplorerPage active={isExplorer} />
              </div>
            )}
            {!isExplorer && (
              <div className="absolute inset-0 overflow-y-auto scroll-thin">
                <Suspense fallback={<div className="p-6"><LoadingBlock lines={6} label="Ekran yükleniyor…" /></div>}>
                  {route === "overview" && <OverviewPage />}
                  {route === "lab" && <LabPage />}
                  {route === "models" && <ModelsPage />}
                  {route === "data" && <DataPage />}
                </Suspense>
              </div>
            )}
          </main>
        </div>
      </div>
      <Sheet open={mobileSheet === "nav"} onOpenChange={(o) => setMobileSheet(o ? "nav" : null)}>
        <SheetContent side="left" className="w-[280px] bg-surface border-line p-0">
          <SheetHeader className="border-b border-line">
            <SheetTitle><Brand /></SheetTitle>
            <SheetDescription className="sr-only">Ekranlar arasında gezinme</SheetDescription>
          </SheetHeader>
          <div className="p-3"><NavList collapsed={false} onNavigate={() => setMobileSheet(null)} /></div>
        </SheetContent>
      </Sheet>
    </TooltipProvider>
  );
}
