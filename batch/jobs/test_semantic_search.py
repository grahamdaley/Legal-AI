"""Test semantic search across court cases and legislation."""

import argparse
import asyncio
import json
from typing import List, Dict, Any

import asyncpg
import boto3

from config.settings import get_settings


def generate_query_embedding(query: str) -> List[float]:
    """Generate embedding for search query."""
    settings = get_settings()
    
    client = boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    
    body = json.dumps({
        "inputText": query,
        "dimensions": 1024,
        "normalize": True,
    })
    
    response = client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    
    result = json.loads(response["body"].read())
    return result["embedding"]


async def search_court_cases(query_embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
    """Search court cases using vector similarity."""
    settings = get_settings()
    conn = await asyncpg.connect(settings.supabase_db_url)
    
    # Convert embedding list to pgvector string format
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'
    
    try:
        results = await conn.fetch(
            """
            SELECT 
                c.id::text,
                c.neutral_citation,
                c.case_name,
                c.decision_date,
                c.court_code,
                e.chunk_type,
                e.chunk_text,
                1 - (e.embedding <=> $1::vector) as similarity_score
            FROM case_embeddings_cohere e
            JOIN court_cases c ON c.id = e.case_id
            WHERE e.embedding IS NOT NULL
            ORDER BY e.embedding <=> $1::vector
            LIMIT $2
            """,
            embedding_str,
            limit,
        )
        
        return [dict(r) for r in results]
        
    finally:
        await conn.close()


async def search_legislation(query_embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
    """Search legislation using vector similarity."""
    settings = get_settings()
    conn = await asyncpg.connect(settings.supabase_db_url)
    
    # Convert embedding list to pgvector string format
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'
    
    try:
        results = await conn.fetch(
            """
            SELECT 
                l.chapter_number::text as chapter,
                l.title_en as title,
                s.section_number,
                s.title as section_title,
                s.content as section_text,
                e.chunk_text,
                1 - (e.embedding <=> $1::vector) as similarity_score
            FROM legislation_embeddings_cohere e
            JOIN legislation_sections s ON s.id = e.section_id
            JOIN legislation l ON l.id = s.legislation_id
            WHERE e.embedding IS NOT NULL
            ORDER BY e.embedding <=> $1::vector
            LIMIT $2
            """,
            embedding_str,
            limit,
        )
        
        return [dict(r) for r in results]
        
    finally:
        await conn.close()


def display_results(query: str, case_results: List[Dict], legislation_results: List[Dict]):
    """Display search results."""
    
    print("=" * 80)
    print(f"SEMANTIC SEARCH RESULTS")
    print("=" * 80)
    print(f'Query: "{query}"')
    print("=" * 80)
    print()
    
    print("🏛️  COURT CASES")
    print("-" * 80)
    
    if not case_results:
        print("No matching cases found.\n")
    else:
        for i, r in enumerate(case_results, 1):
            print(f"{i}. {r['neutral_citation'] or 'N/A'} - {r['case_name']}")
            print(f"   Court: {r['court_code']} | Date: {r['decision_date']}")
            print(f"   Similarity: {r['similarity_score']:.4f}")
            snippet = r['chunk_text'][:200] + "..." if len(r['chunk_text']) > 200 else r['chunk_text']
            print(f"   {snippet}")
            print()
    
    print("📜 LEGISLATION")
    print("-" * 80)
    
    if not legislation_results:
        print("No matching legislation found.\n")
    else:
        for i, r in enumerate(legislation_results, 1):
            print(f"{i}. Cap. {r['chapter']} - {r['title']}")
            print(f"   Section: {r['section_number']} - {r['section_title'] or 'N/A'}")
            print(f"   Similarity: {r['similarity_score']:.4f}")
            snippet = r['chunk_text'][:200] + "..." if len(r['chunk_text']) > 200 else r['chunk_text']
            print(f"   {snippet}")
            print()
    
    print("=" * 80)


async def test_search(query: str, num_cases: int = 5, num_legislation: int = 5):
    """Run semantic search test."""
    print(f'Generating embedding for: "{query}"')
    query_embedding = generate_query_embedding(query)
    print(f"✓ Generated {len(query_embedding)}-dimensional embedding\n")
    
    print("Searching court cases...")
    case_results = await search_court_cases(query_embedding, limit=num_cases)
    print(f"✓ Found {len(case_results)} cases\n")
    
    print("Searching legislation...")
    legislation_results = await search_legislation(query_embedding, limit=num_legislation)
    print(f"✓ Found {len(legislation_results)} sections\n")
    
    display_results(query, case_results, legislation_results)


def main():
    parser = argparse.ArgumentParser(description="Test semantic search")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--cases", type=int, default=5, help="Number of cases (default: 5)")
    parser.add_argument("--legislation", type=int, default=5, help="Number of legislation (default: 5)")
    
    args = parser.parse_args()
    
    asyncio.run(test_search(args.query, args.cases, args.legislation))


if __name__ == "__main__":
    main()
