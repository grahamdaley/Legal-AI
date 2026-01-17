import type { Collection, CollectionItem } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function getCollections(token: string): Promise<Collection[]> {
  const response = await fetch(`${API_URL}/collections`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Failed to get collections");
  }

  const data = await response.json();
  return data.collections;
}

export async function getCollection(
  id: string,
  token: string
): Promise<Collection & { items: CollectionItem[] }> {
  const response = await fetch(`${API_URL}/collections/${id}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Failed to get collection");
  }

  return response.json();
}

export async function createCollection(
  data: { name: string; description?: string; is_public?: boolean },
  token: string
): Promise<Collection> {
  const response = await fetch(`${API_URL}/collections`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Failed to create collection");
  }

  return response.json();
}

export async function updateCollection(
  id: string,
  data: { name?: string; description?: string; is_public?: boolean },
  token: string
): Promise<Collection> {
  const response = await fetch(`${API_URL}/collections/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Failed to update collection");
  }

  return response.json();
}

export async function deleteCollection(id: string, token: string): Promise<void> {
  const response = await fetch(`${API_URL}/collections/${id}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Failed to delete collection");
  }
}

export async function addItemToCollection(
  collectionId: string,
  item: { item_type: "case" | "legislation"; item_id: string; notes?: string },
  token: string
): Promise<CollectionItem> {
  const response = await fetch(`${API_URL}/collections/${collectionId}/items`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(item),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Failed to add item to collection");
  }

  return response.json();
}

export async function removeItemFromCollection(
  collectionId: string,
  itemId: string,
  token: string
): Promise<void> {
  const response = await fetch(
    `${API_URL}/collections/${collectionId}/items/${itemId}`,
    {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || "Failed to remove item from collection");
  }
}
