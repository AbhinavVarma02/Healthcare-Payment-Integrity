import { StrictMode, Suspense, lazy, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, BarChart3, BookOpenText, ChartNoAxesColumnIncreasing, ChevronRight, ClipboardList,
  Database, FlaskConical, LayoutDashboard, Menu, MessageSquareText, Moon, ShieldCheck,
  SlidersHorizontal, Sun, Terminal, WalletCards, X,
} from "lucide-react";
import { Empty, PageHeading } from "./components";
import { studyData } from "./contracts";
import type { Study } from "./contracts";
import { Explorer, Finance, Methods, Models, Overview, Planner, Replay, Validation } from "./pages";
import { ResearchExtensions } from "./research";
import { ReviewPreview } from "./review-preview";
import { Analyst } from "./analyst";
import "./styles.css";

const localMode = import.meta.env.DEV;
const LocalWorkflows = import.meta.env.DEV
  ? lazy(() => import("./local").then(({ LocalWorkflows: Component }) => ({ default: Component })))
  : null;
const Operations = import.meta.env.DEV
  ? lazy(() => import("./operations").then(({ Operations: Component }) => ({ default: Component })))
  : null;

const navigation = [
  { key: "overview", text: "Overview", Icon: LayoutDashboard, Page: Overview },
  { key: "data", text: "Data explorer", Icon: Database, Page: Explorer },
  { key: "models", text: "Risk models", Icon: BarChart3, Page: Models },
  { key: "planner", text: "Audit planner", Icon: SlidersHorizontal, Page: Planner },
  { key: "replay", text: "Policy replay", Icon: FlaskConical, Page: Replay },
  { key: "finance", text: "Financial analysis", Icon: WalletCards, Page: Finance },
  { key: "validation", text: "Validation", Icon: ShieldCheck, Page: Validation },
  { key: "evidence", text: "Policy and lifecycle lab", Icon: Activity, Page: ResearchExtensions },
  { key: "review", text: "Review simulation", Icon: ClipboardList, Page: ReviewPreview },
  { key: "analyst", text: "Analyst", Icon: MessageSquareText, Page: Analyst },
  { key: "methods", text: "Methodology", Icon: BookOpenText, Page: Methods },
];
const groups = [
  { name: "Research", keys: ["overview", "data", "models", "validation"] },
  { name: "Audit strategy", keys: ["planner", "replay", "finance"] },
  { name: "Workflows", keys: ["review", "analyst"] },
  { name: "Study records", keys: ["evidence", "methods"] },
];
const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
type Theme = "light" | "dark";

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem("payment-integrity-theme");
    if (saved === "dark" || saved === "light") return saved;
  } catch { /* The system theme is still available if storage is restricted. */ }
  return systemTheme.matches ? "dark" : "light";
}

let followsSystem = true;
try {
  const saved = localStorage.getItem("payment-integrity-theme");
  followsSystem = saved !== "light" && saved !== "dark";
} catch { /* Storage is optional. */ }
document.documentElement.dataset.theme = initialTheme();

function activeRoute() {
  const route = window.location.hash.replace(/^#\/?/, "");
  return route || "overview";
}

function Workspace() {
  const [route, setRoute] = useState(activeRoute);
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState(initialTheme);
  const [study, setStudy] = useState<Study>();
  const [status, setStatus] = useState("Loading study…");
  const [attempt, setAttempt] = useState(0);
  const showLocal = route === "local" && localMode;
  const showOperations = route === "operations" && localMode;
  const needsStudy = !showLocal && !showOperations;
  useEffect(() => {
    const change = () => { if (followsSystem) setTheme(systemTheme.matches ? "dark" : "light"); };
    systemTheme.addEventListener("change", change);
    return () => systemTheme.removeEventListener("change", change);
  }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  const otherTheme = theme === "dark" ? "light" : "dark";
  function toggleTheme() {
    followsSystem = false;
    setTheme(otherTheme);
    try { localStorage.setItem("payment-integrity-theme", otherTheme); } catch { /* Theme works for this visit. */ }
  }
  useEffect(() => {
    if (!needsStudy || study) return;
    const controller = new AbortController();
    studyData(controller.signal).then((value) => {
      setStudy(value); setStatus("");
    }, (failure: Error) => { if (!controller.signal.aborted) setStatus(failure.message); });
    return () => controller.abort();
  }, [attempt, needsStudy, study]);
  useEffect(() => {
    function onNavigate() {
      setRoute(activeRoute());
      setOpen(false);
      window.scrollTo(0, 0);
      document.getElementById("main")?.focus({ preventScroll: true });
    }
    window.addEventListener("hashchange", onNavigate);
    return () => window.removeEventListener("hashchange", onNavigate);
  }, []);
  const current = navigation.find((item) => item.key === route);
  const section = groups.find((group) => group.keys.includes(route))?.name ?? (needsStudy ? "Workspace" : "Local tools");
  const routeName = current?.text ?? (showLocal ? "Local workflows" : showOperations ? "Operations" : "Workspace");
  const Page = current?.Page;
  function closeNavigation(key: string) {
    if (open && route === key) {
      document.getElementById("main")?.focus({ preventScroll: true });
    }
    setOpen(false);
  }
  return <div className="workspace">
    <a className="skip" href="#main" onClick={(event) => {
      event.preventDefault(); document.getElementById("main")?.focus();
    }}>Skip to content</a>
    <aside className={`sidebar ${open ? "open" : ""}`} onKeyDown={(event) => {
      if (open && event.key === "Escape") {
        setOpen(false);
        document.getElementById("nav-toggle")?.focus();
      }
    }}>
      <a className="identity" href="#/overview">
        <span className="mark"><ChartNoAxesColumnIncreasing size={19} aria-hidden="true" /></span>
        <span>Healthcare<br /><strong>Payment Integrity</strong></span>
      </a>
      <button id="nav-toggle" className="nav-toggle" aria-expanded={open} aria-controls="navigation"
        aria-label={open ? "Close navigation" : "Open navigation"} onClick={() => setOpen(!open)}>
        {open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
      </button>
      <nav id="navigation" className="navigation" aria-label="Workspace">
        {groups.map(({ name, keys }) => <div className="nav-group" key={name}>
          <p>{name}</p>
          {keys.map((key) => {
            const { text, Icon } = navigation.find((item) => item.key === key)!;
            return <a href={`#/${key}`} key={key} onClick={() => closeNavigation(key)}
              aria-current={route === key ? "page" : undefined}>
              <Icon size={16} aria-hidden="true" /><span>{text}</span>
            </a>;
          })}
        </div>)}
        {localMode && <div className="nav-group"><p>Local tools</p>
          <a href="#/local" onClick={() => closeNavigation("local")} aria-current={showLocal ? "page" : undefined}>
            <Terminal size={16} aria-hidden="true" /><span>Local workflows</span></a>
          <a href="#/operations" onClick={() => closeNavigation("operations")} aria-current={showOperations ? "page" : undefined}>
            <ClipboardList size={16} aria-hidden="true" /><span>Operations</span></a>
        </div>}
      </nav>
      <div className="side-note"><Database size={16} aria-hidden="true" /><div>CMS CERT study<span>Release v1.0.0</span></div></div>
    </aside>
    <div className="surface">
      <header className="topbar">
        <div className="location"><span>{section}</span><ChevronRight size={13} aria-hidden="true" /><strong>{routeName}</strong></div>
        <div className="masthead-actions">
          <span className="source-label">{localMode ? <Terminal size={14} aria-hidden="true" /> : <Database size={14} aria-hidden="true" />}
            {localMode ? "Local workspace" : "Static study"}</span>
          <button className="icon-button" type="button" onClick={toggleTheme} aria-label={`Switch to ${otherTheme} theme`}
            title={`Switch to ${otherTheme} theme`}>{theme === "dark" ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}</button>
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        {showOperations && Operations ? <Suspense fallback={<p role="status">Loading operations…</p>}>
          <Operations />
        </Suspense> : showLocal && LocalWorkflows ? <Suspense fallback={<p role="status">Loading local workflows…</p>}>
          <LocalWorkflows />
        </Suspense> : !study
          ? <div className="loading" role="status"><p>{status}</p>
            {status !== "Loading study…" && <button className="button" onClick={() => {
              setStatus("Loading study…"); setAttempt(attempt + 1);
            }}>Retry load</button>}</div>
          : Page ? <Page study={study} />
            : <><PageHeading eyebrow="Workspace" title="Page unavailable" description="Choose a page from the workspace navigation." />
              <Empty text={["local", "operations"].includes(route) ? "This workspace is available in local mode." : "This view does not exist."} /></>}
      </main>
      <footer className="footer"><span>Healthcare Payment Integrity</span><a href="#/methods">Study methods and sources</a></footer>
    </div>
  </div>;
}

const root = document.getElementById("root");
if (root) createRoot(root).render(<StrictMode><Workspace /></StrictMode>);
