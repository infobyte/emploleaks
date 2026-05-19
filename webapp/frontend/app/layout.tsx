"use client";

import { Geist, Geist_Mono } from "next/font/google";
import { useState, useEffect } from "react";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [companyId, setCompanyId] = useState<number | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem("emploleaks_company_id");
    if (saved) setCompanyId(parseInt(saved));
  }, []);

  const handleCompanyChange = (id: number) => {
    setCompanyId(id);
    localStorage.setItem("emploleaks_company_id", String(id));
  };

  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <head>
        <title>EmploLeaks</title>
      </head>
      <body className="h-full flex">
        <Sidebar companyId={companyId} onCompanyChange={handleCompanyChange} />
        <main className="flex-1 overflow-auto p-8">
          {companyId ? (
            <CompanyContext.Provider value={companyId}>{children}</CompanyContext.Provider>
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-5xl mb-4">🏢</p>
                <h2 className="text-xl font-semibold mb-2">Select a Company</h2>
                <p className="text-text-secondary">
                  Choose a company from the sidebar to get started.
                </p>
              </div>
            </div>
          )}
        </main>
      </body>
    </html>
  );
}

import { createContext, useContext } from "react";
export const CompanyContext = createContext<number>(0);
export function useCompanyId() {
  return useContext(CompanyContext);
}
