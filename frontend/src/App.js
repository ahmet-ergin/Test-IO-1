import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AppProvider } from "@/context/AppContext";
import AppShell from "@/components/AppShell";
import Dashboard from "@/pages/Dashboard";
import Devices from "@/pages/Devices";
import Recorder from "@/pages/Recorder";
import Sessions from "@/pages/Sessions";
import RecordedSteps from "@/pages/RecordedSteps";
import Settings from "@/pages/Settings";
import Planned from "@/pages/Planned";

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/devices" element={<Devices />} />
            <Route path="/recorder" element={<Recorder />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/recorded-steps" element={<RecordedSteps />} />
            <Route path="/recorded-steps/:sessionId" element={<RecordedSteps />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/locator-inspector" element={<Planned module="locator" />} />
            <Route path="/ai-analysis" element={<Planned module="ai" />} />
            <Route path="/code-generator" element={<Planned module="codegen" />} />
            <Route path="/jira-integration" element={<Planned module="jira" />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="bottom-right" />
    </AppProvider>
  );
}
