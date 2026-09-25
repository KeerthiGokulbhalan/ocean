import { Anchor } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import AlertsDropdown from "./AlertsDropdown";
import { useAuth } from "../context/AuthContext";

const links = [
  { to: "/", label: "Route Planner" },
  { to: "/fleet", label: "Fleet Dashboard" },
  { to: "/history", label: "Voyage History" },
];

export default function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <header className="bg-navy px-6 py-4 shadow-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-amber text-navy">
            <Anchor className="h-4 w-4" aria-hidden="true" />
          </span>
          <span className="text-lg font-bold text-white">SeaPath</span>
        </div>

        {user && (
          <nav className="flex gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === "/"}
                className={({ isActive }) =>
                  `rounded-md px-3 py-2 text-sm font-medium transition ${
                    isActive ? "bg-white/10 text-white" : "text-slate-300 hover:text-white"
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
        )}

        <div className="flex items-center gap-3">
          {user ? (
            <>
              <AlertsDropdown />
              <span className="text-sm text-slate-300">{user.name}</span>
              <button
                onClick={handleLogout}
                className="rounded-md bg-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/20"
              >
                Log out
              </button>
            </>
          ) : (
            <NavLink
              to="/login"
              className="rounded-md bg-amber px-3 py-1.5 text-xs font-semibold text-navy hover:bg-amber/90"
            >
              Sign in
            </NavLink>
          )}
        </div>
      </div>
    </header>
  );
}
