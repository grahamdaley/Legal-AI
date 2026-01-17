const AWS_REGION = Deno.env.get("AWS_REGION") || "us-east-1";
const AWS_ACCESS_KEY_ID = Deno.env.get("AWS_ACCESS_KEY_ID") || "";
const AWS_SECRET_ACCESS_KEY = Deno.env.get("AWS_SECRET_ACCESS_KEY") || "";

const EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0";
const MAX_TOKENS = 8192;
const EMBEDDING_DIMENSIONS = 1024;

function getSignatureKey(
  key: string,
  dateStamp: string,
  regionName: string,
  serviceName: string
): Promise<ArrayBuffer> {
  const encoder = new TextEncoder();
  return crypto.subtle
    .importKey("raw", encoder.encode("AWS4" + key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"])
    .then((keyData) => crypto.subtle.sign("HMAC", keyData, encoder.encode(dateStamp)))
    .then((dateKey) =>
      crypto.subtle.importKey("raw", dateKey, { name: "HMAC", hash: "SHA-256" }, false, ["sign"])
    )
    .then((dateKeyData) => crypto.subtle.sign("HMAC", dateKeyData, encoder.encode(regionName)))
    .then((regionKey) =>
      crypto.subtle.importKey("raw", regionKey, { name: "HMAC", hash: "SHA-256" }, false, ["sign"])
    )
    .then((regionKeyData) => crypto.subtle.sign("HMAC", regionKeyData, encoder.encode(serviceName)))
    .then((serviceKey) =>
      crypto.subtle.importKey("raw", serviceKey, { name: "HMAC", hash: "SHA-256" }, false, ["sign"])
    )
    .then((serviceKeyData) => crypto.subtle.sign("HMAC", serviceKeyData, encoder.encode("aws4_request")));
}

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

function truncateToTokenLimit(text: string, maxTokens: number = 7500): string {
  const maxChars = maxTokens * 3;
  if (text.length <= maxChars) {
    return text;
  }
  let truncated = text.slice(0, maxChars);
  const lastSpace = truncated.lastIndexOf(" ");
  if (lastSpace > maxChars * 0.8) {
    truncated = truncated.slice(0, lastSpace);
  }
  return truncated.trimEnd();
}

export async function generateEmbedding(text: string): Promise<number[]> {
  if (!AWS_ACCESS_KEY_ID || !AWS_SECRET_ACCESS_KEY) {
    throw new Error("AWS credentials not configured");
  }

  const safeText = truncateToTokenLimit(text, MAX_TOKENS - 500);
  const body = JSON.stringify({
    inputText: safeText,
    dimensions: EMBEDDING_DIMENSIONS,
    normalize: true,
  });

  const service = "bedrock-runtime";
  const host = `${service}.${AWS_REGION}.amazonaws.com`;
  const endpoint = `https://${host}/model/${EMBEDDING_MODEL}/invoke`;
  const method = "POST";

  const now = new Date();
  const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, "");
  const dateStamp = amzDate.slice(0, 8);

  const canonicalUri = `/model/${EMBEDDING_MODEL}/invoke`;
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
    const errorText = await response.text();
    throw new Error(`Bedrock API error: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  return result.embedding as number[];
}
