// Analiz çıktısını dışa aktarma (sunucu tarafı rapor: Markdown özet, CSV tablo, JSON tam rapor).
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

export function ExportMenu({ base, label = "Dışa aktar", testId }: { base: string; label?: string; testId?: string }) {
  const sep = base.includes("?") ? "&" : "?";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" data-testid={testId}><Download /> {label}</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem asChild><a href={`${base}${sep}format=md`} download>Analiz özeti (Markdown)</a></DropdownMenuItem>
        <DropdownMenuItem asChild><a href={`${base}${sep}format=csv`} download>Küme tablosu (CSV)</a></DropdownMenuItem>
        <DropdownMenuItem asChild><a href={`${base}${sep}format=json`} download>Tam rapor (JSON)</a></DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
