import "./globals.css";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata = {
  title: "NYC Traffic Intelligence",
  description: "Upload dashcam videos and analyze congestion + behavior events."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">NYC Traffic Intelligence</Link>
          <nav>
            <Link href="/upload">Upload</Link>
            <Link href="/jobs">Jobs</Link>
          </nav>
        </header>
        <div className="page-shell">{children}</div>
      </body>
    </html>
  );
}
