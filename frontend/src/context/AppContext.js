import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { DICTS } from "@/i18n/strings";
import { http } from "@/lib/api";

const AppCtx = createContext(null);

export function AppProvider({ children }) {
  const [lang, setLang] = useState(localStorage.getItem("amts.lang") || "tr");
  const [theme, setTheme] = useState(localStorage.getItem("amts.theme") || "dark");
  const [status, setStatus] = useState(null);
  const [statusError, setStatusError] = useState(null);

  useEffect(() => {
    localStorage.setItem("amts.lang", lang);
    document.documentElement.lang = lang;
  }, [lang]);
  useEffect(() => {
    localStorage.setItem("amts.theme", theme);
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const refreshStatus = useCallback(async () => {
    try {
      const { data } = await http.get("/status");
      setStatus(data);
      setStatusError(null);
    } catch (e) {
      setStatusError(e.message);
    }
  }, []);

  useEffect(() => {
    refreshStatus();
    const id = setInterval(refreshStatus, 2000);
    return () => clearInterval(id);
  }, [refreshStatus]);

  const t = useCallback((k) => DICTS[lang][k] ?? DICTS.en[k] ?? k, [lang]);

  return (
    <AppCtx.Provider value={{ lang, setLang, theme, setTheme, t, status, statusError, refreshStatus }}>
      {children}
    </AppCtx.Provider>
  );
}

export const useApp = () => useContext(AppCtx);
