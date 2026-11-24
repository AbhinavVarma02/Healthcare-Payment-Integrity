import { StrictMode, Suspense, lazy, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, BarChart3, BookOpenText, Database, FlaskConical, LayoutDashboard, Menu,
  ShieldCheck, SlidersHorizontal, Terminal, WalletCards, X,
} from "lucide-react";
import { Empty, PageHeading } from "./components";
import { studyData } from "./contracts";
import type { Study } from "./contracts";
import { Explorer, Finance, Methods, Models, Overview, Planner, Replay, Validation } from "./pages";
import "./styles.css";

const localMode = import.meta.env.DEV;
const LocalWorkflows = import.meta.env.DEV
  ? lazy(() => import("./local").then(({ LocalWorkflows: Component }) => ({ default: Component })))
  : null;

const navigation = [
  { key: "overview", text: "Overview", Icon: LayoutDashboard, Page: Overview },
  { key: "data", text: "Data explorer", Icon: Database, Page: Explorer },
  { key: "models", text: "Risk models", Icon: BarChart3, Page: Models },
  { key: "planner", text: "Audit planner", Icon: SlidersHorizontal, Page: Planner },
  { key: "replay", text: "Policy replay", Icon: FlaskConical, Page: Replay },
  { key: "finance", text: "Financial analysis", Icon: WalletCards, Page: Finance },
  { key: "validation", text: "Validation", Icon: ShieldCheck, Page: Validation },
  { key: "methods", text: "Methodology", Icon: BookOpenText, Page: Methods },
];

function activeRoute() {
  const route = window.location.hash.replace(/^#\/?/, "");
  return route || "overview";
}

function Workspace() {
  const [route, setRoute] = useState(activeRoute);
  const [open, setOpen] = useState(false);
  const [study, setStudy] = useState<Study>();
  const [status, setStatus] = useState("Loading study…");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    studyData(controller.signal).then((value) => {
      setStudy(value); setStatus("");
    }, (failure: Error) => { if (!controller.signal.aborted) setStatus(failure.message); });
    return () => controller.abort();
  }, [attempt]);
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
  const showLocal = route === "local" && localMode;
  const Page = current?.Page;
  return <div className="workspace">
    <a className="skip" href="#main" onClick={(event) => {
      event.preventDefault(); document.getElementById("main")?.focus();
    }}>Skip to content</a>
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <a className="identity" href="#/overview">
        <span className="mark"><Activity size={24} aria-hidden="true" /></span>
        <span>Healthcare<br /><strong>Payment Integrity</strong></span>
      </a>
      <button className="nav-toggle" aria-expanded={open} aria-controls="navigation"
        aria-label={open ? "Close navigation" : "Open navigation"} onClick={() => setOpen(!open)}>
        {open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
      </button>
      <nav id="navigation" className="navigation" aria-label="Workspace">
        <p>ANALYST WORKSPACE</p>
        {navigation.map(({ key, text, Icon }) => <a href={`#/${key}`} key={key}
          onClick={() => setOpen(false)} aria-current={route === key ? "page" : undefined}>
          <Icon size={18} aria-hidden="true" /><span>{text}</span>
        </a>)}
        {localMode && <a href="#/local" onClick={() => setOpen(false)}
          aria-current={showLocal ? "page" : undefined}><Terminal size={18} aria-hidden="true" /><span>Local workflows</span></a>}
      </nav>
      <div className="side-note"><span className="mode-light" />{localMode ? "Local mode" : "Static study"}<span>CMS CERT · Research use</span></div>
    </aside>
    <div className="surface">
      <header className="topbar"><span>{current?.text ?? (showLocal ? "Local workflows" : "Workspace")}</span>
        <span className="source-label"><span className="mode-light" />{localMode ? "Local research" : "Precomputed results"}</span>
      </header>
      <main id="main" tabIndex={-1}>
        {showLocal && LocalWorkflows ? <Suspense fallback={<p role="status">Loading local workflows…</p>}>
          <LocalWorkflows />
        </Suspense> : !study
          ? <div className="loading" role="status"><p>{status}</p>
            {status !== "Loading study…" && <button className="button" onClick={() => {
              setStatus("Loading study…"); setAttempt(attempt + 1);
            }}>Retry load</button>}</div>
          : Page ? <Page study={study} />
            : <><PageHeading eyebrow="Workspace" title="Page unavailable" description="Choose a page from the workspace navigation." />
              <Empty text={route === "local" ? "Live inference is available in the project’s local mode." : "This view does not exist."} /></>}
      </main>
      <footer className="footer"><span>Healthcare Payment Integrity</span><a href="#/methods">Study methods and sources</a></footer>
    </div>
  </div>;
}

const root = document.getElementById("root");
if (root) createRoot(root).render(<StrictMode><Workspace /></StrictMode>);
