import { NextRequest, NextResponse } from "next/server";

const SUPABASE_FUNCTIONS_URL = process.env.NEXT_PUBLIC_API_URL;

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; itemId: string }> }
) {
  try {
    const { id, itemId } = await params;
    const authHeader = request.headers.get("Authorization");

    const response = await fetch(
      `${SUPABASE_FUNCTIONS_URL}/collections/${id}/items/${itemId}`,
      {
        method: "DELETE",
        headers: {
          ...(authHeader && { Authorization: authHeader }),
        },
      }
    );

    if (!response.ok) {
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    }

    return new NextResponse(null, { status: 204 });
  } catch (error) {
    console.error("Collection item proxy error:", error);
    return NextResponse.json(
      { error: { message: "Internal server error" } },
      { status: 500 }
    );
  }
}
