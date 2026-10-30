import { useRef, useState } from "react";
import { Download, Save, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const FORMAT = "amts-codegen-profile";

export const ProfileManager = ({ profileKey, cfg, store, onSelect }) => {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const fileRef = useRef(null);
  const isUser = profileKey.startsWith("POM:user:");

  const save = () => {
    if (!name.trim()) return;
    const key = store.addUser(name.trim(), store.baseOf(profileKey), cfg);
    setOpen(false); setName(""); onSelect(key);
    toast.success("Profil bu tarayıcıya kaydedildi");
  };

  const exportProfile = () => {
    const data = { format: FORMAT, version: 1, name: store.nameOf(profileKey).replace(/^Kullanıcı: /, ""), baseProfile: store.baseOf(profileKey), config: cfg };
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    a.download = `${data.name.replace(/[^\w-]+/g, "_") || "profil"}.amts-profile.json`;
    a.click(); URL.revokeObjectURL(a.href);
  };

  const importProfile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      if (data.format !== FORMAT || typeof data.config !== "object" || !data.name) throw new Error("format");
      onSelect(store.addUser(`${data.name}`.slice(0, 60), data.baseProfile || "GENERIC", data.config));
      toast.success(`'${data.name}' profili içe aktarıldı`);
    } catch { toast.error("Geçersiz profil dosyası (AMTS profil JSON'u bekleniyor)"); }
  };

  const remove = () => {
    if (!window.confirm("Bu kullanıcı profili silinsin mi?")) return;
    store.removeUser(profileKey.split(":")[2]);
    onSelect(`POM:${store.baseOf(profileKey)}`);
  };

  return (
    <div className="mb-2 flex flex-wrap gap-1" data-testid="cg-profile-manager">
      <Button size="sm" variant="outline" className="h-7 text-[11px]" data-testid="cg-profile-save" onClick={() => setOpen(true)}><Save className="mr-1 h-3 w-3" />Profil olarak kaydet</Button>
      <Button size="sm" variant="outline" className="h-7 text-[11px]" data-testid="cg-profile-export" onClick={exportProfile}><Download className="mr-1 h-3 w-3" />Dışa aktar</Button>
      <Button size="sm" variant="outline" className="h-7 text-[11px]" data-testid="cg-profile-import" onClick={() => fileRef.current?.click()}><Upload className="mr-1 h-3 w-3" />İçe aktar</Button>
      <input ref={fileRef} type="file" accept=".json,application/json" className="hidden" data-testid="cg-profile-import-input" onChange={importProfile} />
      {isUser && <Button size="sm" variant="ghost" className="h-7 text-[11px] text-red-500" data-testid="cg-profile-delete" onClick={remove}><Trash2 className="mr-1 h-3 w-3" />Sil</Button>}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="cg-profile-save-dialog">
          <DialogHeader><DialogTitle>Kullanıcı profili olarak kaydet</DialogTitle></DialogHeader>
          <Input data-testid="cg-profile-name" placeholder="Profil adı" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && save()} />
          <p className="text-xs text-muted-foreground">Profil yalnızca bu tarayıcıda saklanır; başka bir bilgisayara taşımak için "Dışa aktar"ı kullanın.</p>
          <DialogFooter><Button data-testid="cg-profile-save-confirm" disabled={!name.trim()} onClick={save}>Kaydet</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
