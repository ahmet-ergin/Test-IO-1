import { FileCode2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

export const CodePreview = ({ files, original, active, onSelect, onEdit, onReset }) => {
  const f = files[active];
  if (!f) return null;
  const dirty = (i) => files[i].content !== original[i]?.content;
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
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="truncate font-mono text-[10px] text-muted-foreground" data-testid="cg-file-path">{f.path}</span>
        {dirty(active) && <Button size="sm" variant="ghost" className="h-6 text-[11px]" data-testid="cg-file-reset" onClick={() => onReset(active)}>
          <RotateCcw className="mr-1 h-3 w-3" />Üretilen hâline dön</Button>}
      </div>
      <textarea data-testid="cg-editor" spellCheck={false} value={f.content} onChange={(e) => onEdit(active, e.target.value)}
        className="block h-[560px] w-full resize-y bg-background p-3 font-mono text-[12px] leading-[1.55] text-foreground outline-none" />
    </div>
  );
};
