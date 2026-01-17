"use client";

import { AlertCircle, RefreshCw, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import Link from "next/link";

interface ErrorDisplayProps {
  title?: string;
  message?: string;
  statusCode?: number;
  onRetry?: () => void;
  backUrl?: string;
  backLabel?: string;
}

export function ErrorDisplay({
  title,
  message,
  statusCode,
  onRetry,
  backUrl,
  backLabel = "Go back",
}: ErrorDisplayProps) {
  const getErrorInfo = () => {
    switch (statusCode) {
      case 400:
        return {
          title: "Bad Request",
          message: "The request was invalid. Please check your input and try again.",
        };
      case 401:
        return {
          title: "Unauthorized",
          message: "You need to sign in to access this resource.",
        };
      case 403:
        return {
          title: "Forbidden",
          message: "You don't have permission to access this resource.",
        };
      case 404:
        return {
          title: "Not Found",
          message: "The resource you're looking for doesn't exist.",
        };
      case 429:
        return {
          title: "Too Many Requests",
          message: "You've made too many requests. Please wait a moment and try again.",
        };
      case 500:
        return {
          title: "Server Error",
          message: "Something went wrong on our end. Please try again later.",
        };
      case 503:
        return {
          title: "Service Unavailable",
          message: "The service is temporarily unavailable. Please try again later.",
        };
      default:
        return {
          title: title || "Error",
          message: message || "An unexpected error occurred.",
        };
    }
  };

  const errorInfo = getErrorInfo();

  return (
    <Card className="max-w-md mx-auto">
      <CardHeader className="text-center">
        <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
        <CardTitle className="text-destructive">
          {statusCode && <span className="text-4xl block mb-2">{statusCode}</span>}
          {errorInfo.title}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-center space-y-4">
        <p className="text-sm text-muted-foreground">{errorInfo.message}</p>
        <div className="flex flex-col sm:flex-row gap-2 justify-center">
          {backUrl && (
            <Link href={backUrl}>
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                {backLabel}
              </Button>
            </Link>
          )}
          {onRetry && (
            <Button onClick={onRetry}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Try Again
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
