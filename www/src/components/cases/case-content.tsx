"use client";

import { useState } from "react";
import { FileText, BookOpen, Link2 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import type { CaseDetail } from "@/types";

interface CaseContentProps {
  caseData: CaseDetail;
}

export function CaseContent({ caseData }: CaseContentProps) {
  const [activeTab, setActiveTab] = useState("summary");

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="summary" className="gap-2">
          <BookOpen className="h-4 w-4" />
          <span className="hidden sm:inline">Summary</span>
        </TabsTrigger>
        <TabsTrigger value="judgment" className="gap-2">
          <FileText className="h-4 w-4" />
          <span className="hidden sm:inline">Full Judgment</span>
        </TabsTrigger>
        <TabsTrigger value="citations" className="gap-2">
          <Link2 className="h-4 w-4" />
          <span className="hidden sm:inline">Citations</span>
        </TabsTrigger>
      </TabsList>

      <TabsContent value="summary" className="mt-4">
        <Card>
          <CardContent className="pt-6">
            {caseData.headnote ? (
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <p className="whitespace-pre-wrap leading-relaxed">
                  {caseData.headnote}
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground italic">
                No AI-generated summary available for this case.
              </p>
            )}
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="judgment" className="mt-4">
        <Card>
          <CardContent className="pt-6">
            {caseData.full_text ? (
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
                  {caseData.full_text}
                </pre>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground italic">
                Full judgment text is not available. Please view the original
                document on the Judiciary website.
              </p>
            )}
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="citations" className="mt-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground italic">
              Citation network analysis coming soon. This feature will show
              cases cited by this judgment and cases that cite this judgment.
            </p>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
}
