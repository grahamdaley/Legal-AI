const AWS_REGION = Deno.env.get("AWS_REGION") || "us-east-1";
const AWS_ACCESS_KEY_ID = Deno.env.get("AWS_ACCESS_KEY_ID") || "";
const AWS_SECRET_ACCESS_KEY = Deno.env.get("AWS_SECRET_ACCESS_KEY") || "";

const HAIKU_MODEL = "anthropic.claude-3-haiku-20240307-v1:0";

export interface EnhancedQuery {
  originalQuery: string;
  expandedQuery: string;
  legalConcepts: string[];
  jurisdiction?: string;
  caseType?: string;
  suggestedFilters?: {
    court?: string;
    yearRange?: [number, number];
  };
}

const QUERY_ENHANCEMENT_PROMPT = `You are a legal search query enhancer for Hong Kong law. Given a user's search query, analyze it and provide enhancements to improve search results.

Respond in JSON format only with these fields:
- expandedQuery: The original query with relevant legal synonyms and related terms added
- legalConcepts: Array of key legal concepts/doctrines identified
- jurisdiction: Detected jurisdiction reference if any (e.g., "Hong Kong", "UK", "Common Law")
- caseType: Type of case if identifiable (e.g., "criminal", "civil", "family", "commercial", "constitutional")
- suggestedFilters: Object with optional court code and yearRange [fromYear, toYear]

Hong Kong court codes: CFA (Court of Final Appeal), CA (Court of Appeal), CFI (Court of First Instance), DC (District Court), FC (Family Court), LT (Lands Tribunal), LAB (Labour Tribunal)

Common abbreviations to expand:
- CFA → Court of Final Appeal
- BL → Basic Law
- BoR → Bill of Rights
- JR → Judicial Review
- PI → Personal Injury
- RTA → Road Traffic Accident

Example input: "wrongful dismissal employment"
Example output:
{
  "expandedQuery": "wrongful dismissal employment termination unfair dismissal breach of employment contract",
  "legalConcepts": ["wrongful dismissal", "employment law", "breach of contract"],
  "caseType": "civil",
  "suggestedFilters": { "court": "LAB" }
}

User query: `;

function toHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function sha256(message: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(message);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return toHex(hash);
}

async function getSignatureKey(
  key: string,
  dateStamp: string,
  regionName: string,
  serviceName: string
): Promise<ArrayBuffer> {
  const encoder = new TextEncoder();
  const kDate = await crypto.subtle.sign(
    "HMAC",
    await crypto.subtle.importKey("raw", encoder.encode("AWS4" + key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]),
    encoder.encode(dateStamp)
  );
  const kRegion = await crypto.subtle.sign(
    "HMAC",
    await crypto.subtle.importKey("raw", kDate, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]),
    encoder.encode(regionName)
  );
  const kService = await crypto.subtle.sign(
    "HMAC",
    await crypto.subtle.importKey("raw", kRegion, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]),
    encoder.encode(serviceName)
  );
  return crypto.subtle.sign(
    "HMAC",
    await crypto.subtle.importKey("raw", kService, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]),
    encoder.encode("aws4_request")
  );
}

export async function enhanceQuery(query: string): Promise<EnhancedQuery> {
  if (!AWS_ACCESS_KEY_ID || !AWS_SECRET_ACCESS_KEY) {
    return {
      originalQuery: query,
      expandedQuery: query,
      legalConcepts: [],
    };
  }

  const body = JSON.stringify({
    anthropic_version: "bedrock-2023-05-31",
    max_tokens: 500,
    messages: [
      {
        role: "user",
        content: QUERY_ENHANCEMENT_PROMPT + query,
      },
    ],
  });

  const service = "bedrock-runtime";
  const host = `${service}.${AWS_REGION}.amazonaws.com`;
  const endpoint = `https://${host}/model/${HAIKU_MODEL}/invoke`;
  const method = "POST";

  const now = new Date();
  const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, "");
  const dateStamp = amzDate.slice(0, 8);

  const canonicalUri = `/model/${HAIKU_MODEL}/invoke`;
  const canonicalQuerystring = "";
  const payloadHash = await sha256(body);

  const canonicalHeaders = `content-type:application/json\nhost:${host}\nx-amz-date:${amzDate}\n`;
  const signedHeaders = "content-type;host;x-amz-date";

  const canonicalRequest = [
    method,
    canonicalUri,
    canonicalQuerystring,
    canonicalHeaders,
    signedHeaders,
    payloadHash,
  ].join("\n");

  const algorithm = "AWS4-HMAC-SHA256";
  const credentialScope = `${dateStamp}/${AWS_REGION}/${service}/aws4_request`;
  const stringToSign = [
    algorithm,
    amzDate,
    credentialScope,
    await sha256(canonicalRequest),
  ].join("\n");

  const signingKey = await getSignatureKey(AWS_SECRET_ACCESS_KEY, dateStamp, AWS_REGION, service);
  const signatureBuffer = await crypto.subtle.sign(
    "HMAC",
    await crypto.subtle.importKey("raw", signingKey, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]),
    new TextEncoder().encode(stringToSign)
  );
  const signature = toHex(signatureBuffer);

  const authorizationHeader = `${algorithm} Credential=${AWS_ACCESS_KEY_ID}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

  try {
    const response = await fetch(endpoint, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-Amz-Date": amzDate,
        Authorization: authorizationHeader,
      },
      body,
    });

    if (!response.ok) {
      console.error("Query enhancement failed:", await response.text());
      return {
        originalQuery: query,
        expandedQuery: query,
        legalConcepts: [],
      };
    }

    const result = await response.json();
    const content = result.content?.[0]?.text || "";
    
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return {
        originalQuery: query,
        expandedQuery: query,
        legalConcepts: [],
      };
    }

    const parsed = JSON.parse(jsonMatch[0]);
    
    return {
      originalQuery: query,
      expandedQuery: parsed.expandedQuery || query,
      legalConcepts: parsed.legalConcepts || [],
      jurisdiction: parsed.jurisdiction,
      caseType: parsed.caseType,
      suggestedFilters: parsed.suggestedFilters,
    };
  } catch (error) {
    console.error("Query enhancement error:", error);
    return {
      originalQuery: query,
      expandedQuery: query,
      legalConcepts: [],
    };
  }
}
