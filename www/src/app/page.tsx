import Link from "next/link";
import { Scale, Search, BookOpen, Gavel, Shield, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="flex flex-col">
      <section className="container flex flex-col items-center justify-center gap-6 py-24 md:py-32">
        <div className="flex items-center gap-3">
          <Scale className="h-12 w-12 text-primary" />
          <h1 className="text-4xl font-bold tracking-tight md:text-5xl">
            Legal AI
          </h1>
        </div>
        <p className="max-w-2xl text-center text-lg text-muted-foreground">
          AI-powered legal research platform for Hong Kong case law and
          legislation. Search through thousands of court judgments and
          legislative documents with semantic understanding.
        </p>

        <div className="flex flex-wrap justify-center gap-4 mt-8">
          <Link href="/login">
            <Button size="lg" className="gap-2">
              Sign in to get started
            </Button>
          </Link>
          <Link href="/signup">
            <Button variant="outline" size="lg" className="gap-2">
              Create an account
            </Button>
          </Link>
        </div>
      </section>

      <section className="border-t bg-muted/50">
        <div className="container py-16">
          <h2 className="text-2xl font-semibold text-center mb-8">
            Powerful Legal Research Features
          </h2>
          <div className="grid gap-8 md:grid-cols-3">
            <div className="flex flex-col items-center text-center p-6">
              <Search className="h-10 w-10 text-primary mb-4" />
              <h3 className="font-semibold mb-2">Semantic Search</h3>
              <p className="text-sm text-muted-foreground">
                Find relevant cases using natural language queries. Our AI
                understands legal concepts and context.
              </p>
            </div>
            <div className="flex flex-col items-center text-center p-6">
              <Gavel className="h-10 w-10 text-primary mb-4" />
              <h3 className="font-semibold mb-2">Case Law Database</h3>
              <p className="text-sm text-muted-foreground">
                Access Hong Kong court judgments from CFA, CA, CFI, and other
                courts with AI-generated summaries.
              </p>
            </div>
            <div className="flex flex-col items-center text-center p-6">
              <BookOpen className="h-10 w-10 text-primary mb-4" />
              <h3 className="font-semibold mb-2">Legislation Library</h3>
              <p className="text-sm text-muted-foreground">
                Browse Hong Kong ordinances, regulations, and subsidiary
                legislation with full-text search.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t">
        <div className="container py-16">
          <h2 className="text-2xl font-semibold text-center mb-8">
            Why Choose Legal AI?
          </h2>
          <div className="grid gap-8 md:grid-cols-2 max-w-4xl mx-auto">
            <div className="flex gap-4 p-6">
              <Shield className="h-8 w-8 text-primary flex-shrink-0" />
              <div>
                <h3 className="font-semibold mb-2">Secure & Private</h3>
                <p className="text-sm text-muted-foreground">
                  Your research is protected. All searches and saved items are
                  private to your account.
                </p>
              </div>
            </div>
            <div className="flex gap-4 p-6">
              <FolderOpen className="h-8 w-8 text-primary flex-shrink-0" />
              <div>
                <h3 className="font-semibold mb-2">Organize Your Research</h3>
                <p className="text-sm text-muted-foreground">
                  Create collections to save and organize cases and legislation
                  for your matters.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t bg-primary text-primary-foreground">
        <div className="container py-12 text-center">
          <h2 className="text-xl font-semibold mb-4">
            Ready to streamline your legal research?
          </h2>
          <Link href="/signup">
            <Button size="lg" variant="secondary">
              Get started for free
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
