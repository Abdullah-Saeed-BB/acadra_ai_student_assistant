"use client";

import {
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AcadraLogo } from "@/components/acadra-mark";

type NavIconProps = {
  className?: string;
};

function NavIcon({
  children,
  className,
}: NavIconProps & { children: ReactNode }) {
  return (
    <svg
      className={className ? `nav-icon ${className}` : "nav-icon"}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true">
      {children}
    </svg>
  );
}

function TodayIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </NavIcon>
  );
}

function UpcomingIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <rect x="3" y="4.5" width="18" height="16" rx="2.5" />
      <path d="M3 9.5h18M8 2.5v4M16 2.5v4" />
    </NavIcon>
  );
}

function BacklogIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <path d="M12 3 3 7.5l9 4.5 9-4.5L12 3Z" />
      <path d="M3 12.5 12 17l9-4.5M3 16.5 12 21l9-4.5" />
    </NavIcon>
  );
}

function TasksIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <path d="m7.5 12 2.5 2.5L16 8.5" />
    </NavIcon>
  );
}

function InboxIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <path d="M3 13h4l1.5 2.5h7L17 13h4" />
      <path d="M5.5 5h13l2.5 8v4.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V13l2.5-8Z" />
    </NavIcon>
  );
}

function CoursesIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <path d="M4 4.5h5.5A2.5 2.5 0 0 1 12 7v13a2.2 2.2 0 0 0-2.2-2.2H4V4.5Z" />
      <path d="M20 4.5h-5.5A2.5 2.5 0 0 0 12 7v13a2.2 2.2 0 0 1 2.2-2.2H20V4.5Z" />
    </NavIcon>
  );
}

function AddSourceIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v8M8 12h8" />
    </NavIcon>
  );
}

function ConnectorsIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </NavIcon>
  );
}

function SettingsIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
      <circle cx="16" cy="7" r="2.5" />
      <circle cx="8" cy="17" r="2.5" />
    </NavIcon>
  );
}

function SimulatorIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <path d="M12 3.5 13.8 9l5.7 1.8L13.8 12.6 12 18.5l-1.8-5.9L4.5 10.8 10.2 9 12 3.5Z" />
      <path d="M19 16.5l.7 2.3 2.3.7-2.3.7-.7 2.3-.7-2.3-2.3-.7 2.3-.7.7-2.3Z" />
    </NavIcon>
  );
}

function CollapseIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      className="nav-icon"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <path d="M9 4v16" />
      <path
        d={collapsed ? "m13.5 9.5 2.5 2.5-2.5 2.5" : "m16 9.5-2.5 2.5 2.5 2.5"}
      />
    </svg>
  );
}

type NavItem = {
  href: string;
  label: string;
  icon: (props: NavIconProps) => ReactNode;
};

type NavGroup = {
  title: string;
  items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
  {
    title: "Plan",
    items: [
      { href: "/", label: "Today", icon: TodayIcon },
      { href: "/upcoming", label: "Upcoming", icon: UpcomingIcon },
      { href: "/backlog", label: "Backlog", icon: BacklogIcon },
      { href: "/tasks", label: "All tasks", icon: TasksIcon },
    ],
  },
  {
    title: "What changed",
    items: [
      { href: "/inbox", label: "Inbox", icon: InboxIcon },
      { href: "/courses", label: "Courses", icon: CoursesIcon },
      { href: "/sources/new", label: "Add source", icon: AddSourceIcon },
      { href: "/connecters", label: "Connectors", icon: ConnectorsIcon },
    ],
  },
  {
    title: "Workspace",
    items: [
      { href: "/settings", label: "Settings", icon: SettingsIcon },
      {
        href: "/alexa+_simulator",
        label: "Alexa+ simulator",
        icon: SimulatorIcon,
      },
    ],
  },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return (
    pathname === href ||
    (pathname.startsWith(`${href}/`) && pathname !== "tasks")
  );
}

const COLLAPSE_STORAGE_KEY = "acadra:sidebar-collapsed";

/**
 * Tiny external store for the collapsed preference: localStorage is the source
 * of truth so the rail keeps its state across reloads and browser tabs, while
 * `useSyncExternalStore` keeps the server render stable (always expanded).
 */
const collapseStore = {
  listeners: new Set<() => void>(),
  read(): boolean {
    return window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === "true";
  },
  write(next: boolean) {
    window.localStorage.setItem(COLLAPSE_STORAGE_KEY, String(next));
    collapseStore.listeners.forEach((listener) => listener());
  },
  subscribe(listener: () => void) {
    collapseStore.listeners.add(listener);
    window.addEventListener("storage", listener);
    return () => {
      collapseStore.listeners.delete(listener);
      window.removeEventListener("storage", listener);
    };
  },
};

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const collapsed = useSyncExternalStore(
    collapseStore.subscribe,
    collapseStore.read,
    () => false,
  );

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <aside
      className={
        collapsed
          ? open
            ? "sidebar is-collapsed is-open"
            : "sidebar is-collapsed"
          : open
            ? "sidebar is-open"
            : "sidebar"
      }>
      <div className="sidebar-top">
        <Link href="/" className="brand" aria-label="Acadra home">
          <AcadraLogo />
        </Link>
        <button
          type="button"
          className="sidebar-collapse"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          aria-controls="primary-navigation"
          onClick={() => collapseStore.write(!collapsed)}>
          <CollapseIcon collapsed={collapsed} />
        </button>
        <button
          type="button"
          className="nav-toggle"
          aria-expanded={open}
          aria-controls="primary-navigation"
          onClick={() => setOpen((value) => !value)}>
          {open ? "Close" : "Menu"}
        </button>
      </div>

      <nav
        id="primary-navigation"
        className={open ? "sidebar-nav open" : "sidebar-nav"}
        aria-label="Primary">
        {NAV_GROUPS.map((group) => (
          <div className="nav-group" key={group.title}>
            <p className="nav-group-title">{group.title}</p>
            {group.items.map((item) => {
              const active = isActive(pathname, item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={active ? "nav-item active" : "nav-item"}
                  aria-current={active ? "page" : undefined}
                  title={item.label}
                  onClick={() => setOpen(false)}>
                  <Icon />
                  <span className="nav-item-label">{item.label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      {open ? (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Close menu"
          tabIndex={-1}
          onClick={() => setOpen(false)}
        />
      ) : null}
    </aside>
  );
}
