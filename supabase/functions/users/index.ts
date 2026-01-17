import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { corsHeaders, handleCors } from "../_shared/cors.ts";
import { badRequest, unauthorized, notFound, serverError } from "../_shared/errors.ts";
import { getSupabaseClientWithAuth } from "../_shared/db.ts";

interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  organization: string | null;
  subscription_tier: string;
  preferences: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface QuotaInfo {
  daily_limit: number;
  used_today: number;
  remaining: number;
  resets_at: string;
}

interface UpdateProfileRequest {
  full_name?: string;
  organization?: string;
  preferences?: Record<string, unknown>;
}

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
    const endpoint = pathParts[pathParts.length - 1];

    if (endpoint === "me") {
      if (req.method === "GET") {
        return await getProfile(supabase, user.id);
      } else if (req.method === "PATCH") {
        const body: UpdateProfileRequest = await req.json();
        return await updateProfile(supabase, user.id, body);
      } else {
        return badRequest("Method not allowed. Use GET or PATCH.");
      }
    } else if (endpoint === "quota") {
      if (req.method === "GET") {
        return await getQuota(supabase, user.id);
      } else {
        return badRequest("Method not allowed. Use GET.");
      }
    } else {
      return notFound("Endpoint not found");
    }
  } catch (error) {
    console.error("Users API error:", error);
    return serverError(
      error instanceof Error ? error.message : "An unexpected error occurred"
    );
  }
});

async function getProfile(
  supabase: ReturnType<typeof getSupabaseClientWithAuth>,
  userId: string
): Promise<Response> {
  const { data, error } = await supabase
    .from("user_profiles")
    .select("id, email, full_name, organization, subscription_tier, preferences, created_at, updated_at")
    .eq("id", userId)
    .single();

  if (error) {
    if (error.code === "PGRST116") {
      return notFound("User profile not found");
    }
    throw new Error(`Failed to fetch profile: ${error.message}`);
  }

  const profile: UserProfile = data as UserProfile;

  return new Response(JSON.stringify(profile), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

async function updateProfile(
  supabase: ReturnType<typeof getSupabaseClientWithAuth>,
  userId: string,
  updates: UpdateProfileRequest
): Promise<Response> {
  const allowedFields: (keyof UpdateProfileRequest)[] = ["full_name", "organization", "preferences"];
  const updateData: Record<string, unknown> = {};

  for (const field of allowedFields) {
    if (updates[field] !== undefined) {
      updateData[field] = updates[field];
    }
  }

  if (Object.keys(updateData).length === 0) {
    return badRequest("No valid fields to update");
  }

  const { data, error } = await supabase
    .from("user_profiles")
    .update(updateData)
    .eq("id", userId)
    .select("id, email, full_name, organization, subscription_tier, preferences, created_at, updated_at")
    .single();

  if (error) {
    throw new Error(`Failed to update profile: ${error.message}`);
  }

  return new Response(JSON.stringify(data), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

async function getQuota(
  supabase: ReturnType<typeof getSupabaseClientWithAuth>,
  userId: string
): Promise<Response> {
  const { data, error } = await supabase.rpc("get_user_quota", {
    p_user_id: userId,
  });

  if (error) {
    throw new Error(`Failed to fetch quota: ${error.message}`);
  }

  if (!data || data.length === 0) {
    return notFound("User quota not found");
  }

  const quota: QuotaInfo = {
    daily_limit: data[0].daily_limit,
    used_today: data[0].used_today,
    remaining: data[0].remaining,
    resets_at: data[0].resets_at,
  };

  return new Response(JSON.stringify(quota), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
