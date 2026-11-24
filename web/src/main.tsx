import { StrictMode, Suspense, lazy, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BookOpenText, ChartNoAxesColumnIncreasing, ChartSpline, ChevronRight, ClipboardCheck, Cpu, Database, FlaskConical,
  LayoutDashboard, ListChecks, Menu, Moon, Repeat2, ScanSearch, ShieldCheck, SlidersHorizontal, Sun, WalletCards, X,
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
  { key: "models", text: "Risk models", Icon: ChartSpline, Page: Models },
  { key: "validation", text: "Validation", Icon: ShieldCheck, Page: Validation },
  { key: "planner", text: "Audit planner", Icon: SlidersHorizontal, Page: Planner },
  { key: "replay", text: "Policy replay", Icon: Repeat2, Page: Replay },
  { key: "finance", text: "Financial scenarios", Icon: WalletCards, Page: Finance },
  { key: "review", text: "Review simulation", Icon: ClipboardCheck, Page: ReviewPreview },
  { key: "analyst", text: "Analyst", Icon: ScanSearch, Page: Analyst },
  { key: "evidence", text: "Research extensions", Icon: FlaskConical, Page: ResearchExtensions },
  { key: "methods", text: "Methods", Icon: BookOpenText, Page: Methods },
];
const localPages = [
  { key: "operations", text: "Operations", Icon: ListChecks },
  { key: "local", text: "Scoring and replay", Icon: Cpu },
];
const groups = [
  { name: "Study", keys: ["overview", "data", "models", "validation"] },
  { name: "Audit strategy", keys: ["planner", "replay", "finance"] },
  { name: "Workflows", keys: ["review", "analyst"] },
  { name: "Evidence", keys: ["evidence", "methods"] },
];
const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
type Theme = "light" | "dark";

function savedTheme(): Theme | null {
  try {
    const saved = localStorage.getItem("payment-integrity-theme");
    return saved === "dark" || saved === "light" ? saved : null;
  } catch { return null; }
}
let followsSystem = savedTheme() === null;
const initialTheme = (): Theme => savedTheme() ?? (systemTheme.matches ? "dark" : "light");
document.documentElement.dataset.theme = initialTheme();

function activeRoute() {
  return window.location.hash.replace(/^#\/?/, "") || "overview";
}

function Workspace() {
  const [route, setRoute] = useState(activeRoute);
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState(initialTheme);
  const [study, setStudy] = useState<Study>();
  const [status, setStatus] = useState("");
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
    try { localStorage.setItem("payment-integrity-theme", otherTheme); } catch { /* The theme still applies for this visit. */ }
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
  const localPage = localMode ? localPages.find((item) => item.key === route) : undefined;
  const section = groups.find((group) => group.keys.includes(route))?.name ?? (localPage ? "Local workspace" : "Workspace");
  const routeName = current?.text ?? localPage?.text ?? "Page unavailable";
  const Page = current?.Page;
  useEffect(() => {
    document.title = `${routeName} · Healthcare Payment Integrity`;
  }, [routeName]);
  function closeNavigation(key: string) {
    if (open && route === key) document.getElementById("main")?.focus({ preventScroll: true });
    setOpen(false);
  }
  const link = (key: string, text: string, Icon: typeof Database) => <a href={`#/${key}`} key={key}
    onClick={() => closeNavigation(key)} aria-current={route === key ? "page" : undefined}>
    <Icon size={16} strokeWidth={1.75} aria-hidden="true" /><span>{text}</span>
  </a>;
  return <div className="workspace">
    <a className="skip" href="#main" onClick={(event) => {
      event.preventDefault(); document.getElementById("main")?.focus();
    }}>Skip to content</a>
    <aside className={`sidebar ${open ? "open" : ""}`} onKeyDown={(event) => {
      if (open && event.key === "Escape") {
        setOpen(false);
        document.getElementById("nav-toggle")?.focus();
      }
    }}><div className="sidebar-inner">
      <a className="identity" href="#/overview">
        <span className="mark"><ChartNoAxesColumnIncreasing size={17} strokeWidth={2.25} aria-hidden="true" /></span>
        <span className="wordmark"><small>Healthcare</small> <strong>Payment Integrity</strong></span>
      </a>
      <button id="nav-toggle" type="button" className="nav-toggle" aria-expanded={open} aria-controls="navigation"
        aria-label={open ? "Close navigation" : "Open navigation"} onClick={() => setOpen(!open)}>
        {open ? <X size={19} aria-hidden="true" /> : <Menu size={19} aria-hidden="true" />}
      </button>
      <nav id="navigation" className="navigation" aria-label="Workspace">
        {groups.map(({ name, keys }) => <div className="nav-group" key={name}>
          <p>{name}</p>
          {keys.map((key) => {
            const { text, Icon } = navigation.find((item) => item.key === key)!;
            return link(key, text, Icon);
          })}
        </div>)}
        {localMode && <div className="nav-group"><p>Local workspace</p>
          {localPages.map(({ key, text, Icon }) => link(key, text, Icon))}
        </div>}
      </nav>
      <div className="release">
        <span><strong>Release v1.0.0</strong></span>
        <span>{study ? `Protocol ${study.protocol} · ${study.cohorts.length} CERT releases` : "CMS CERT research study"}</span>
      </div>
    </div></aside>
    <div className="surface">
      <header className="topbar">
        <div className="location"><span>{section}</span><ChevronRight size={13} aria-hidden="true" /><strong>{routeName}</strong></div>
        <div className="masthead-actions">
          {localMode
            ? <span className="mode live" title="Local mode. Workflows call the loopback research API.">Local workspace <small>Live API</small></span>
            : <span className="mode" title="Static mode. Results are precomputed and no backend is contacted.">Static release <small>Precomputed results</small></span>}
          <button className="icon-button" type="button" onClick={toggleTheme} aria-label={`Switch to ${otherTheme} theme`}
            title={`Switch to ${otherTheme} theme`}>{theme === "dark" ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}</button>
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        {showOperations && Operations ? <Suspense fallback={<p className="loading" role="status">Loading operations</p>}>
          <Operations />
        </Suspense> : showLocal && LocalWorkflows ? <Suspense fallback={<p className="loading" role="status">Loading local tools</p>}>
          <LocalWorkflows />
        </Suspense> : !study
          ? status ? <div className="loading failed" role="alert">
            <h2>The study could not be opened</h2>
            <p>{status}</p>
            <p className="quiet">The page needs study.json from the same folder. Check the static server, then retry.</p>
            <button className="button" type="button" onClick={() => { setStatus(""); setAttempt(attempt + 1); }}>Retry load</button>
          </div> : <div className="loading" role="status">
            <p>Loading the reviewed study aggregate</p><div className="skeleton" aria-hidden="true"><span /><span /><span /></div>
          </div>
          : Page ? <Page study={study} />
            : <><PageHeading title="Page unavailable" description={["local", "operations"].includes(route)
              ? "This page needs the local workspace and its loopback API." : "This address does not match a page in the workspace."}
              aside={<a className="button secondary" href="#/overview">Go to the overview</a>} />
              <Empty text="Choose a page from the workspace navigation." /></>}
      </main>
      <footer className="footer"><span>Healthcare Payment Integrity · Research prototype. Not for payment or coverage decisions.</span>
        <a href="#/methods">Methods and sources</a></footer>
    </div>
  </div>;
}

const root = document.getElementById("root");
if (root) createRoot(root).render(<StrictMode><Workspace /></StrictMode>);
