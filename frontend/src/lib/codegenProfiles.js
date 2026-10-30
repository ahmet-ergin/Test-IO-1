import { useCallback, useEffect, useState } from "react";
import { http } from "@/lib/api";

// Built-in profile definitions live in the backend code (GET /codegen/pom/profiles); only user edits are kept in the browser.
const USER_KEY = "amts.codegen.pom.userProfiles";
export const PROFILE_KEY = "amts.codegen.profile";
const POM_STORAGE = { GENERIC: "amts.codegen.pom.config.v1" };
const GAUGE_STORAGE = "amts.codegen.config.v1";

export const merge = (def, saved) => Object.fromEntries(Object.entries(def).map(([k, v]) => [k,
  v && typeof v === "object" && !Array.isArray(v) ? merge(v, saved?.[k] || {}) : (saved?.[k] !== undefined ? saved[k] : v)]));
const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };

export const initialProfile = () => {
  const v = localStorage.getItem(PROFILE_KEY);
  if (v === "CUCUMBER_POM") return "POM:GENERIC";
  return v || "GAUGE";
};

export const describe = (key) => {
  if (!key || key === "GAUGE") return { kind: "GAUGE", base: "/codegen" };
  const [, a, b] = key.split(":");
  return a === "user" ? { kind: "POM", base: "/codegen/pom", userId: b } : { kind: "POM", base: "/codegen/pom", builtinId: a };
};

export const useProfiles = () => {
  const [builtins, setBuiltins] = useState(null);
  const [users, setUsers] = useState(() => read(USER_KEY, []));
  useEffect(() => { http.get("/codegen/pom/profiles").then((r) => setBuiltins(r.data)).catch(() => setBuiltins([])); }, []);
  const saveUsers = (list) => { setUsers(list); localStorage.setItem(USER_KEY, JSON.stringify(list)); };

  const options = [["GAUGE", "Gauge + Appium 2"], ...(builtins || []).map((p) => [`POM:${p.id}`, p.name]),
    ...users.map((u) => [`POM:user:${u.id}`, `Kullanıcı: ${u.name}`])];

  const baseDefaults = useCallback((builtinId) => (builtins || []).find((p) => p.id === builtinId)?.config, [builtins]);

  const defaultsFor = useCallback((key) => {
    const d = describe(key);
    if (d.kind === "GAUGE" || !builtins) return null;
    if (d.userId) {
      const u = users.find((x) => x.id === d.userId);
      return u ? baseDefaults(u.baseProfile) || baseDefaults("GENERIC") : null;
    }
    return baseDefaults(d.builtinId) || null;
  }, [builtins, users, baseDefaults]);

  const loadCfg = useCallback((key, defaults) => {
    const d = describe(key);
    if (d.kind === "GAUGE") return merge(defaults, read(GAUGE_STORAGE, {}));
    if (d.userId) return merge(defaults, users.find((x) => x.id === d.userId)?.config || {});
    return merge(defaults, read(POM_STORAGE[d.builtinId] || `amts.codegen.pom.${d.builtinId}.v1`, {}));
  }, [users]);

  const saveCfg = (key, cfg) => {
    const d = describe(key);
    if (d.kind === "GAUGE") localStorage.setItem(GAUGE_STORAGE, JSON.stringify(cfg));
    else if (d.userId) saveUsers(users.map((u) => (u.id === d.userId ? { ...u, config: cfg } : u)));
    else localStorage.setItem(POM_STORAGE[d.builtinId] || `amts.codegen.pom.${d.builtinId}.v1`, JSON.stringify(cfg));
  };

  const clearCfg = (key, defaults) => {
    const d = describe(key);
    if (d.kind === "GAUGE") localStorage.removeItem(GAUGE_STORAGE);
    else if (d.userId) saveUsers(users.map((u) => (u.id === d.userId ? { ...u, config: defaults } : u)));
    else localStorage.removeItem(POM_STORAGE[d.builtinId] || `amts.codegen.pom.${d.builtinId}.v1`);
  };

  const addUser = (name, baseProfile, config) => {
    const id = Math.random().toString(36).slice(2, 10);
    saveUsers([...users, { id, name, baseProfile, config }]);
    return `POM:user:${id}`;
  };
  const removeUser = (id) => saveUsers(users.filter((u) => u.id !== id));
  const baseOf = (key) => { const d = describe(key); return d.userId ? users.find((u) => u.id === d.userId)?.baseProfile || "GENERIC" : d.builtinId; };
  const nameOf = (key) => options.find(([k]) => k === key)?.[1] || key;

  return { builtins, users, options, defaultsFor, loadCfg, saveCfg, clearCfg, addUser, removeUser, baseOf, nameOf };
};
