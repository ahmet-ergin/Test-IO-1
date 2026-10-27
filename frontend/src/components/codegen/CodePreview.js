import { Copy, FileCode2, ListPlus, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

const BEGIN = "// <amts:members>";
const END = "// </amts:members>";

export const membersOf = (content) => {
  const a = content.indexOf(BEGIN), b = content.indexOf(END);
  if (a < 0 || b < a) return null;
  const imports = content.split("\n").filter((l) => l.startsWith("import ")).join("\n");
  const members = content.slice(a + BEGIN.length, b).replace(/^\n/, "").replace(/\s+$/, "");
  return `${imports}\n\n${members}\n`;
};

const copy = async (text, what) => {
  try { await navigator.clipboard.writeText(text); toast.success(`${what} kopyalandı`); } catch { toast.error("Panoya kopyalanamadı"); }
};

export const CodePreview = ({ files, original, active, onSelect, onEdit, onReset }) => {
  const f = files[active];
  if (!f) return null;
  const dirty = (i) => files[i].content !== original[i]?.content;
  const members = membersOf(f.content);
  return (
    <div data-testid="cg-preview" className="overflow-hidden rounded border border-border">
      <div className="flex flex-wrap border-b border-border bg-muted/30">
        {files.map((x, i) => (
          <button key={x.path} type="button" data-testid={`cg-file-tab-${x.role}`} onClick={() => onSelect(i)}
            className={`flex items-center gap-1.5 border-r border-border px-3 py-2 font-mono text-[11px] transition-colors ${i === active ? "bg-background text-primary" : "text-muted-foreground hover:text-foreground"}`}>
            <FileCode2 className="h-3 w-3" />{x.path.split("/").pop()}{dirty(i) && <span className="h-1.5 w-1.5 rounded-full bg-amber-500" data-testid={`cg-file-dirty-${x.role}`} />}
          </button>
        ))}
      </div>
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-1.5">
        <span className="truncate font-mono text-[10px] text-muted-foreground" data-testid="cg-file-path">{f.path}</span>
        <div className="flex shrink-0 gap-1">
          {dirty(active) && <Button size="sm" variant="ghost" className="h-6 text-[11px]" data-testid="cg-file-reset" onClick={() => onReset(active)}>
            <RotateCcw className="mr-1 h-3 w-3" />Üretilen hâline dön</Button>}
          {members && <Button size="sm" variant="ghost" className="h-6 text-[11px]" data-testid="cg-copy-members" onClick={() => copy(members, "Import'lar ve yeni üyeler")}
            title="Mevcut sınıfınıza eklemek için yalnızca import'ları ve // <amts:members> bölümünü kopyalar"><ListPlus className="mr-1 h-3 w-3" />Üyeleri kopyala</Button>}
          <Button size="sm" variant="ghost" className="h-6 text-[11px]" data-testid="cg-copy-file" onClick={() => copy(f.content, "Dosya")}>
            <Copy className="mr-1 h-3 w-3" />Dosyayı kopyala</Button>
        </div>
      </div>
      <textarea data-testid="cg-editor" spellCheck={false} value={f.content} onChange={(e) => onEdit(active, e.target.value)}
        className="block h-[560px] w-full resize-y bg-background p-3 font-mono text-[12px] leading-[1.55] text-foreground outline-none" />
    </div>
  );
};
