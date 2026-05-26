import { Link, Route, Routes, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import ProjectDetail from "./pages/ProjectDetail";
import CreateProject from "./pages/CreateProject";
import Locations from "./pages/Locations";
import { BoxIcon, GlobeIcon, PlusIcon } from "./components/icons";

const links = [
  { to: "/", label: "Projects", icon: BoxIcon },
  { to: "/locations", label: "Locations", icon: GlobeIcon },
  { to: "/new", label: "New Project", icon: PlusIcon },
];

function Navigation({ mobile = false }: { mobile?: boolean }) {
  const location = useLocation();

  return (
    <nav className={mobile ? "flex items-center gap-1" : "mt-10 space-y-2"}>
      {links.map((link) => {
        const Icon = link.icon;
        const active = location.pathname === link.to;

        return (
          <Link
            key={link.to}
            to={link.to}
            className={mobile ? `ghost-button !min-h-9 !px-2 ${active ? "!border-[var(--ink)]" : ""}` : `nav-item ${active ? "nav-item-active" : ""}`}
            title={link.label}
          >
            <Icon className="h-4 w-4" />
            {!mobile && <span className="font-bold">{link.label}</span>}
          </Link>
        );
      })}
    </nav>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <aside className="left-rail">
        <Link to="/" className="flex items-center gap-3">
          <span className="brand-mark">
            <BoxIcon className="h-5 w-5" />
          </span>
          <span>
            <span className="block text-lg font-black leading-none">CapsuleLab</span>
            <span className="eyebrow">local runtime console</span>
          </span>
        </Link>
        <Navigation />
        <div className="absolute bottom-4 left-4 right-4 border-t border-[rgba(24,26,31,0.18)] pt-4">
          <div className="eyebrow">API</div>
          <div className="mt-2 flex items-center gap-2 text-sm font-bold">
            <span className="status-dot status-live" />
            localhost:8000
          </div>
        </div>
      </aside>

      <div>
        <header className="mobile-nav">
          <Link to="/" className="flex items-center gap-2 font-black">
            <span className="brand-mark !h-9 !w-9">
              <BoxIcon className="h-4 w-4" />
            </span>
            CapsuleLab
          </Link>
          <Navigation mobile />
        </header>
        <main className="workspace">
          <div className="workbench">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/locations" element={<Locations />} />
              <Route path="/new" element={<CreateProject />} />
              <Route path="/project/:id" element={<ProjectDetail />} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  );
}
