"use client";

import { Geist, Geist_Mono } from "next/font/google";
import { useState, useEffect, createContext, useContext } from "react";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import { Building2 } from "lucide-react";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const CompanyContext = createContext<number>(0);
export function useCompanyId() {
  return useContext(CompanyContext);
}

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
        <main className="flex-1 overflow-auto p-6">
          {companyId ? (
            <CompanyContext.Provider value={companyId}>{children}</CompanyContext.Provider>
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-bg-secondary border border-border mb-4">
                  <Building2 className="w-6 h-6 text-text-secondary" />
                </div>
                <h2 className="text-lg font-semibold text-text-primary mb-1">Select a Company</h2>
                <p className="text-sm text-text-secondary">
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
