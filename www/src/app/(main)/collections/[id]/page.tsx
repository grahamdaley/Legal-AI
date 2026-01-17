"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Trash2,
  Loader2,
  FileText,
  BookOpen,
  MoreVertical,
  Pencil,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { createClient } from "@/lib/supabase/client";
import {
  getCollection,
  updateCollection,
  deleteCollection,
  removeItemFromCollection,
} from "@/lib/api/collections";
import { toast } from "sonner";
import type { Collection, CollectionItem } from "@/types";

function CollectionDetailSkeleton() {
  return (
    <div className="container py-6">
      <Skeleton className="h-8 w-32 mb-6" />
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-10 w-1/2" />
          <Skeleton className="h-6 w-1/3" />
        </div>
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function CollectionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = params.id as string;
  const supabase = createClient();

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const {
    data: collection,
    isLoading,
    error,
  } = useQuery<Collection & { items: CollectionItem[] }>({
    queryKey: ["collection", id],
    queryFn: async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error("Not authenticated");
      }
      return getCollection(id, session.access_token);
    },
    enabled: !!id,
  });

  const updateMutation = useMutation({
    mutationFn: async (data: { name?: string; description?: string }) => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error("Not authenticated");
      }
      return updateCollection(id, data, session.access_token);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collection", id] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      setIsEditOpen(false);
      toast.success("Collection updated");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to update collection");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error("Not authenticated");
      }
      return deleteCollection(id, session.access_token);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      toast.success("Collection deleted");
      router.push("/collections");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to delete collection");
    },
  });

  const removeItemMutation = useMutation({
    mutationFn: async (itemId: string) => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error("Not authenticated");
      }
      return removeItemFromCollection(id, itemId, session.access_token);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collection", id] });
      toast.success("Item removed from collection");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to remove item");
    },
  });

  const handleEdit = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate({
      name: editName,
      description: editDescription || undefined,
    });
  };

  const openEditDialog = () => {
    if (collection) {
      setEditName(collection.name);
      setEditDescription(collection.description || "");
      setIsEditOpen(true);
    }
  };

  if (isLoading) {
    return <CollectionDetailSkeleton />;
  }

  if (error) {
    return (
      <div className="container py-6">
        <Link href="/collections">
          <Button variant="ghost" size="sm" className="mb-6">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to collections
          </Button>
        </Link>
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          <p className="font-medium">Failed to load collection</p>
          <p className="text-sm">{(error as Error).message}</p>
        </div>
      </div>
    );
  }

  if (!collection) {
    return null;
  }

  return (
    <div className="container py-6">
      <Link href="/collections">
        <Button variant="ghost" size="sm" className="mb-6">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to collections
        </Button>
      </Link>

      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{collection.name}</h1>
            {collection.description && (
              <p className="text-muted-foreground mt-1">
                {collection.description}
              </p>
            )}
            <p className="text-sm text-muted-foreground mt-2">
              {collection.items?.length || 0} item
              {(collection.items?.length || 0) !== 1 ? "s" : ""}
            </p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={openEditDialog}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => setIsDeleteOpen(true)}
                className="text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {collection.items && collection.items.length === 0 ? (
          <div className="text-center py-12 border rounded-lg">
            <p className="text-muted-foreground">
              This collection is empty. Add items from search results or detail
              pages.
            </p>
            <Link href="/search">
              <Button variant="outline" className="mt-4">
                Go to Search
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {collection.items?.map((item) => (
              <Card key={item.id} className="group relative">
                <Link
                  href={
                    item.item_type === "case"
                      ? `/cases/${item.item_id}`
                      : `/legislation/${item.item_id}`
                  }
                >
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                      {item.item_type === "case" ? (
                        <FileText className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <BookOpen className="h-4 w-4 text-muted-foreground" />
                      )}
                      {item.case?.case_name ||
                        item.legislation?.title_en ||
                        "Unknown item"}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="capitalize">
                        {item.item_type}
                      </Badge>
                      {item.case?.neutral_citation && (
                        <span className="text-sm font-mono text-muted-foreground">
                          {item.case.neutral_citation}
                        </span>
                      )}
                      {item.legislation?.chapter_number && (
                        <span className="text-sm font-mono text-muted-foreground">
                          Cap. {item.legislation.chapter_number}
                        </span>
                      )}
                    </div>
                    {item.notes && (
                      <p className="text-sm text-muted-foreground mt-2 italic">
                        {item.notes}
                      </p>
                    )}
                  </CardContent>
                </Link>
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => {
                    e.preventDefault();
                    removeItemMutation.mutate(item.id);
                  }}
                  disabled={removeItemMutation.isPending}
                >
                  {removeItemMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4 text-destructive" />
                  )}
                </Button>
              </Card>
            ))}
          </div>
        )}
      </div>

      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent>
          <form onSubmit={handleEdit}>
            <DialogHeader>
              <DialogTitle>Edit Collection</DialogTitle>
              <DialogDescription>
                Update the name and description of this collection.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label htmlFor="edit-name" className="text-sm font-medium">
                  Name
                </label>
                <Input
                  id="edit-name"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <label
                  htmlFor="edit-description"
                  className="text-sm font-medium"
                >
                  Description
                </label>
                <Textarea
                  id="edit-description"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsEditOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Save
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Collection</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &quot;{collection.name}&quot;?
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
