"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bookmark, Plus, Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { createClient } from "@/lib/supabase/client";
import {
  getCollections,
  createCollection,
  addItemToCollection,
} from "@/lib/api/collections";
import { toast } from "sonner";
import type { Collection } from "@/types";

interface AddToCollectionButtonProps {
  itemType: "case" | "legislation";
  itemId: string;
  itemTitle: string;
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
}

export function AddToCollectionButton({
  itemType,
  itemId,
  itemTitle,
  variant = "outline",
  size = "sm",
}: AddToCollectionButtonProps) {
  const queryClient = useQueryClient();
  const supabase = createClient();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState("");

  const { data: collections } = useQuery<Collection[]>({
    queryKey: ["collections"],
    queryFn: async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        return [];
      }
      return getCollections(session.access_token);
    },
  });

  const addMutation = useMutation({
    mutationFn: async (collectionId: string) => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error("Not authenticated");
      }
      return addItemToCollection(
        collectionId,
        { item_type: itemType, item_id: itemId },
        session.access_token
      );
    },
    onSuccess: (_, collectionId) => {
      queryClient.invalidateQueries({ queryKey: ["collection", collectionId] });
      const collection = collections?.find((c) => c.id === collectionId);
      toast.success(`Added to ${collection?.name || "collection"}`);
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to add to collection");
    },
  });

  const createMutation = useMutation({
    mutationFn: async (name: string) => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error("Not authenticated");
      }
      const collection = await createCollection({ name }, session.access_token);
      await addItemToCollection(
        collection.id,
        { item_type: itemType, item_id: itemId },
        session.access_token
      );
      return collection;
    },
    onSuccess: (collection) => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      setIsCreateOpen(false);
      setNewCollectionName("");
      toast.success(`Created "${collection.name}" and added item`);
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to create collection");
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCollectionName.trim()) return;
    createMutation.mutate(newCollectionName);
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant={variant} size={size}>
            <Bookmark className="mr-2 h-4 w-4" />
            Save
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          {collections && collections.length > 0 ? (
            <>
              {collections.map((collection) => (
                <DropdownMenuItem
                  key={collection.id}
                  onClick={() => addMutation.mutate(collection.id)}
                  disabled={addMutation.isPending}
                >
                  {addMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="mr-2 h-4 w-4 opacity-0" />
                  )}
                  {collection.name}
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
            </>
          ) : null}
          <DropdownMenuItem onClick={() => setIsCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create new collection
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent>
          <form onSubmit={handleCreate}>
            <DialogHeader>
              <DialogTitle>Create Collection</DialogTitle>
              <DialogDescription>
                Create a new collection and add &quot;{itemTitle}&quot; to it.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <Input
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
                placeholder="Collection name"
                required
              />
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsCreateOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Create & Add
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
