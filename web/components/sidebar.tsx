"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AcadraLogo } from "@/components/acadra-mark";

type NavItem = {
  href: string;
  label: string;
};

type NavGroup = {
  title: string;
  items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
  {
    title: "Plan",
    items: [
      { href: "/", label: "Today" },
      { href: "/upcoming", label: "Upcoming" },
      { href: "/backlog", label: "Backlog" },
      { href: "/tasks", label: "All tasks" },
    ],
  },
  {
    title: "What changed",
    items: [
      { href: "/inbox", label: "Inbox" },
      { href: "/courses", label: "Courses" },
      { href: "/sources/new", label: "Add source" },
      { href: "/gmail", label: "Gmail" },
    ],
  },
  {
    title: "Workspace",
    items: [
      { href: "/settings", label: "Settings" },
      { href: "/alexa+_simulator", label: "Alexa+ simulator" },
    ],
  },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <Link href="/" className="brand" aria-label="Acadra home">
          <AcadraLogo />
        </Link>
        <button
          type="button"
          className="nav-toggle"
          aria-expanded={open}
          aria-controls="primary-navigation"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Close" : "Menu"}
        </button>
      </div>

      <nav
        id="primary-navigation"
        className={open ? "sidebar-nav open" : "sidebar-nav"}
        aria-label="Primary"
      >
        {NAV_GROUPS.map((group) => (
          <div className="nav-group" key={group.title}>
            <p className="nav-group-title">{group.title}</p>
            {group.items.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={active ? "nav-item active" : "nav-item"}
                  aria-current={active ? "page" : undefined}
                  onClick={() => setOpen(false)}
                >
                  <span className="nav-waypoint" aria-hidden="true" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
        <p className="nav-hint">
          Every step shows where it came from. Open Inbox to see what changed in your
          sources.
        </p>
      </nav>
    </aside>
  );
}
