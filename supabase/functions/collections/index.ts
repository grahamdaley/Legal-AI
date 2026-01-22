import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { corsHeaders, handleCors } from "../_shared/cors.ts";
import { badRequest, unauthorized, notFound, serverError } from "../_shared/errors.ts";
import { getSupabaseClientWithAuth } from "../_shared/db.ts";

interface Collection {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  is_public: boolean;
  created_at: string;
  updated_at: string;
  item_count?: number;
}

interface CollectionItem {
  id: string;
  collection_id: string;
  item_type: "case" | "legislation";
  item_id: string;
  notes: string | null;
  added_at: string;
  item_details?: Record<string, unknown>;
}

interface CreateCollectionRequest {
  name: string;
  description?: string;
  is_public?: boolean;
}

interface UpdateCollectionRequest {
  name?: string;
  description?: string;
  is_public?: boolean;
}

interface AddItemRequest {
  item_type: "case" | "legislation";
  item_id: string;
  notes?: string;
}

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

serve(async (req: Request) => {
  const corsResponse = handleCors(req);
  if (corsResponse) return corsResponse;

  const authHeader = req.headers.get("Authorization");
  if (!authHeader) {
    return unauthorized("Missing Authorization header");
  }

  try {
    const supabase = getSupabaseClientWithAuth(authHeader);
    
    const { data: { user }, error: authError } = await supabase.auth.getUser();
    if (authError || !user) {
      return unauthorized("Invalid or expired token");
    }

    const url = new URL(req.url);
    const pathParts = url.pathname.split("/").filter(Boolean);
    
    const collectionsIndex = pathParts.indexOf("collections");
    const collectionId = pathParts[collectionsIndex + 1];
    const subResource = pathParts[collectionsIndex + 2];
    const itemId = pathParts[collectionsIndex + 3];

    if (!collectionId) {
      if (req.method === "GET") {
        return await listCollections(supabase, user.id);
      } else if (req.method === "POST") {
        const body: CreateCollectionRequest = await req.json();
        return await createCollection(supabase, user.id, body);
      } else {
        return badRequest("Method not allowed");
      }
    }

    if (!UUID_REGEX.test(collectionId)) {
      return badRequest("Invalid collection ID");
    }

    if (subResource === "items") {
      if (req.method === "POST" && !itemId) {
        const body: AddItemRequest = await req.json();
        return await addItem(supabase, user.id, collectionId, body);
      } else if (req.method === "DELETE" && itemId) {
        if (!UUID_REGEX.test(itemId)) {
          return badRequest("Invalid item ID");
        }
        return await removeItem(supabase, user.id, collectionId, itemId);
      } else {
        return badRequest("Method not allowed");
      }
    }

    if (req.method === "GET") {
      return await getCollection(supabase, user.id, collectionId);
    } else if (req.method === "PATCH") {
      const body: UpdateCollectionRequest = await req.json();
      return await updateCollection(supabase, user.id, collectionId, body);
    } else if (req.method === "DELETE") {
      return await deleteCollection(supabase, user.id, collectionId);
    } else {
      return badRequest("Method not allowed");
    }
  } catch (error) {
    console.error("Collections API error:", error);
    return serverError(
      error instanceof Error ? error.message : "An unexpected error occurred"
    );
  }
});

async function listCollections(
  supabase: ReturnType<typeof getSupabaseClientWithAuth>,
  userId: string
): Promise<Response> {
  const { data, error } = await supabase
    .from("user_collections")
    .select("id, user_id, name, description, is_public, created_at, updated_at")
    .eq("user_id", userId)
    .order("updated_at", { ascending: false });

  if (error) {
    throw new Error(`Failed to list collections: ${error.message}`);
  }

  const collectionsWithCounts = await Promise.all(
    (data || []).map(async (collection) => {
      const { count } = await supabase
        .from("collection_items")
        .select("*", { count: "exact", head: true })
        .eq("collection_id", collection.id);

      return { ...collection, item_count: count || 0 };
    })
  );

  return new Response(JSON.stringify({ collections: collectionsWithCounts }), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

async function createCollection(
  supabase: ReturnType<typeof getSupabaseClientWithAuth>,
  userId: string,
  body: CreateCollectionRequest
): Promise<Response> {
  if (!body.name || body.name.trim().length === 0) {
    return badRequest("Collection name is required");
  }

  const { data, error } = await supabase
    .from("user_collections")
    .insert({
      user_id: userId,
      name: body.name.trim(),
      description: body.description?.trim() || null,
      is_public: body.is_public || false,
    })
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to create collection: ${error.message}`);
  }

  return new Response(JSON.stringify(data), {
    status: 201,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

async function getCollection(
  supabase: ReturnType<typeof getSupabaseClientWithAuth>,
  userId: string,
  collectionId: string
): Promise<Response> {
  const { data: collection, error: collError } = await supabase
    .from("user_collections")
    .select("*")
    .eq("id", collectionId)
    .single();

  if (collError) {
    if (collError.code === "PGRST116") {
      return notFound("Collection not found");
    }
    throw new Error(`Failed to fetch collection: ${collError.message}`);
  }

  if (collection.user_id !== userId && !collection.is_public) {
    return notFound("Collection not found");
  }

  const { data: items, error: itemsError } = await supabase
    .from("collection_items")
    .select("*")
    .eq("collection_id", collectionId)
    .order("added_at", { ascending: false });

  if (itemsError) {
    throw new Error(`Failed to fetch items: ${itemsError.message}`);
  }

  const enrichedItems = await Promise.all(
    (items || []).map(async (item: CollectionItem) => {
      if (item.item_type === "case") {
        const { data } = await supabase
          .from("court_cases")
          .select("id, neutral_citation, case_name, court_code, decision_date, headnote")
          .eq("id", item.item_id)
          .single();
        return { ...item, case: data, legislation: null };
      } else if (item.item_type === "legislation") {
        const { data } = await supabase
          .from("legislation")
          .select("id, chapter_number, title_en, type, status")
          .eq("id", item.item_id)
          .single();
        return { ...item, case: null, legislation: data };
      }
      return { ...item, case: null, legislation: null };
    })
  );

  return new Response(
    JSON.stringify({
      ...collection,
      items: enrichedItems,
      item_count: enrichedItems.length,
    }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" } }
  );
}

async function updateCollection(
  supabase: ReturnType<typeof getSupabaseClientWithAuth>,
  userId: string,
  collectionId: string,
  body: UpdateCollectionRequest
): Promise<Response> {
  const { data: existing } = await supabase
    .from("user_collections")
    .select("user_id")
    .eq("id", collectionId)
    .single();

  if (!existing || existing.user_id !== userId) {
    return notFound("Collection not found");
  }

  const updateData: Record<string, unknown> = {};
  if (body.name !== undefined) updateData.name = body.name.trim();
  if (body.description !== undefined) updateData.description = body.description?.trim() || null;
  if (body.is_public !== undefined) updateData.is_public = body.is_public;

  if (Object.keys(updateData).length === 0) {
    return badRequest("No valid fields to update");
  }

  const { data, error } = await supabase
    .from("user_collections")
    .update(updateData)
    .eq("id", collectionId)
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to update collection: ${error.message}`);
  }

  return new Response(JSON.stringify(data), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

async function deleteCollection(
  supabase: ReturnType<typeof getSupabaseClientWithAuth>,
  userId: string,
  collectionId: string
): Promise<Response> {
  const { data: existing } = await supabase
    .from("user_collections")
    .select("user_id")
    .eq("id", collectionId)
    .single();

  if (!existing || existing.user_id !== userId) {
    return notFound("Collection not found");
  }

  const { error } = await supabase
    .from("user_collections")
    .delete()
    .eq("id", collectionId);

  if (error) {
    throw new Error(`Failed to delete collection: ${error.message}`);
  }

  return new Response(null, { status: 204, headers: corsHeaders });
}

async function addItem(
  supabase: ReturnType<typeof getSupabaseClientWithAuth>,
  userId: string,
  collectionId: string,
  body: AddItemRequest
): Promise<Response> {
  const { data: collection } = await supabase
    .from("user_collections")
    .select("user_id")
    .eq("id", collectionId)
    .single();

  if (!collection || collection.user_id !== userId) {
    return notFound("Collection not found");
  }

  if (!body.item_type || !["case", "legislation"].includes(body.item_type)) {
    return badRequest("Invalid item_type. Must be 'case' or 'legislation'");
  }

  if (!body.item_id || !UUID_REGEX.test(body.item_id)) {
    return badRequest("Invalid item_id");
  }

  const { data, error } = await supabase
    .from("collection_items")
    .insert({
      collection_id: collectionId,
      item_type: body.item_type,
      item_id: body.item_id,
      notes: body.notes?.trim() || null,
    })
    .select()
    .single();

  if (error) {
    if (error.code === "23505") {
      return badRequest("Item already exists in this collection");
    }
    throw new Error(`Failed to add item: ${error.message}`);
  }

  return new Response(JSON.stringify(data), {
    status: 201,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

async function removeItem(
  supabase: ReturnType<typeof getSupabaseClientWithAuth>,
  userId: string,
  collectionId: string,
  itemId: string
): Promise<Response> {
  const { data: collection } = await supabase
    .from("user_collections")
    .select("user_id")
    .eq("id", collectionId)
    .single();

  if (!collection || collection.user_id !== userId) {
    return notFound("Collection not found");
  }

  const { error } = await supabase
    .from("collection_items")
    .delete()
    .eq("id", itemId)
    .eq("collection_id", collectionId);

  if (error) {
    throw new Error(`Failed to remove item: ${error.message}`);
  }

  return new Response(null, { status: 204, headers: corsHeaders });
}
