import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Header } from "@/components/layout/header";
import { Toaster } from "@/components/ui/sonner";
import { ErrorBoundary } from "@/components/ui/error-boundary";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Legal AI - Hong Kong Legal Research",
    template: "%s | Legal AI",
  },
  description:
    "AI-powered legal research platform for Hong Kong case law and legislation. Search through thousands of court judgments and legislative documents with semantic understanding.",
  keywords: [
    "Hong Kong law",
    "legal research",
    "case law",
    "legislation",
    "court judgments",
    "AI legal",
    "legal database",
  ],
  authors: [{ name: "Legal AI" }],
  openGraph: {
    type: "website",
    locale: "en_HK",
    siteName: "Legal AI",
    title: "Legal AI - Hong Kong Legal Research",
    description:
      "AI-powered legal research platform for Hong Kong case law and legislation.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Legal AI - Hong Kong Legal Research",
    description:
      "AI-powered legal research platform for Hong Kong case law and legislation.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Providers>
          <ErrorBoundary>
            <a
              href="#main-content"
              className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md"
            >
              Skip to main content
            </a>
            <div className="relative min-h-screen flex flex-col">
              <Header />
              <main id="main-content" className="flex-1" role="main">
                {children}
              </main>
            </div>
          </ErrorBoundary>
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
