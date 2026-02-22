import "./globals.css";
import Link from "next/link";
import { Montserrat } from "next/font/google";
import type { ReactNode } from "react";

const montserrat = Montserrat({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800"] });

export const metadata = {
  title: "NYC Traffic Intelligence",
  description: "Upload dashcam videos and analyze congestion + behavior events."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={montserrat.className}>
        <div className="bg-orb orb-1" />
        <div className="bg-orb orb-2" />
        <header className="topbar">
          <Link href="/" className="brand">NYC Traffic Intelligence</Link>
          <nav>
            <Link href="/upload" className="nav-link">Upload</Link>
            <Link href="/jobs" className="nav-link">Jobs</Link>
          </nav>
        </header>
        <div className="page-shell">{children}</div>
      </body>
    </html>
  );
}
